import { sql, one, type MemoryRow } from "../db";

/**
 * Long-term memory.
 *
 * Retrieval is Postgres full-text search weighted by importance and how often a
 * fact has actually proven useful (hit_count). No embedding provider needed —
 * one less API key, one less failure mode. If recall quality ever plateaus, the
 * upgrade path is pgvector alongside (not instead of) this ranking.
 */

export interface RememberInput {
  content: string;
  kind?: string;
  subject?: string;
  source?: string;
  clientId?: string | null;
  importance?: number;
  tags?: string[];
}

/** Write a durable fact. Near-duplicates are reinforced rather than re-inserted. */
export async function remember(input: RememberInput): Promise<MemoryRow> {
  const {
    content,
    kind = "fact",
    subject = null,
    source = "agent",
    clientId = null,
    importance = 3,
    tags = [],
  } = input;

  // Reinforce instead of duplicating when we already hold a very similar fact
  // about the same subject.
  const dupe = await one<MemoryRow>(
    `SELECT * FROM memory
      WHERE active = true
        AND ($1::text IS NULL OR subject IS NOT DISTINCT FROM $1)
        AND similarity(content, $2) > 0.75
      ORDER BY similarity(content, $2) DESC
      LIMIT 1`,
    [subject, content],
  );

  if (dupe) {
    const updated = await one<MemoryRow>(
      `UPDATE memory
          SET hit_count  = hit_count + 1,
              importance = GREATEST(importance, $2),
              confidence = LEAST(1.00, confidence + 0.05),
              updated_at = now()
        WHERE id = $1
      RETURNING *`,
      [dupe.id, importance],
    );
    return updated!;
  }

  const row = await one<MemoryRow>(
    `INSERT INTO memory (kind, subject, content, source, client_id, importance, tags)
     VALUES ($1,$2,$3,$4,$5,$6,$7)
     RETURNING *`,
    [kind, subject, content, source, clientId, importance, tags],
  );
  return row!;
}

/**
 * Retrieve memory relevant to a query.
 * Ranked by text relevance x importance x proven usefulness.
 */
export async function recall(
  query: string,
  limit = 12,
): Promise<MemoryRow[]> {
  const trimmed = (query || "").trim();
  if (!trimmed) return topMemories(limit);

  const rows = await sql<MemoryRow>(
    `SELECT *,
            ts_rank(search_vec, websearch_to_tsquery('english', $1)) AS rank
       FROM memory
      WHERE active = true
        AND search_vec @@ websearch_to_tsquery('english', $1)
      ORDER BY (ts_rank(search_vec, websearch_to_tsquery('english', $1))
                * (1 + importance * 0.35)
                * (1 + LEAST(hit_count, 20) * 0.03)) DESC
      LIMIT $2`,
    [trimmed, limit],
  );

  if (rows.length) {
    await touch(rows.map((r) => r.id));
    return rows;
  }

  // Full-text found nothing — fall back to fuzzy match so a slightly-off
  // phrasing still surfaces the right fact.
  const fuzzy = await sql<MemoryRow>(
    `SELECT * FROM memory
      WHERE active = true AND similarity(content, $1) > 0.15
      ORDER BY similarity(content, $1) DESC
      LIMIT $2`,
    [trimmed, limit],
  );
  if (fuzzy.length) await touch(fuzzy.map((r) => r.id));
  return fuzzy;
}

/** Highest-value facts, used when there is no specific query to match against. */
export async function topMemories(limit = 12): Promise<MemoryRow[]> {
  return sql<MemoryRow>(
    `SELECT * FROM memory
      WHERE active = true
      ORDER BY importance DESC, hit_count DESC, updated_at DESC
      LIMIT $1`,
    [limit],
  );
}

export async function memoriesForClient(
  clientId: string,
  limit = 20,
): Promise<MemoryRow[]> {
  return sql<MemoryRow>(
    `SELECT * FROM memory
      WHERE active = true AND client_id = $1
      ORDER BY importance DESC, updated_at DESC
      LIMIT $2`,
    [clientId, limit],
  );
}

/** Mark a fact as superseded by a newer one rather than deleting it. */
export async function supersede(
  oldId: string,
  newContent: string,
  source = "agent",
): Promise<MemoryRow> {
  const prev = await one<MemoryRow>(`SELECT * FROM memory WHERE id = $1`, [oldId]);
  const replacement = await remember({
    content: newContent,
    kind: prev?.kind ?? "fact",
    subject: prev?.subject ?? undefined,
    source,
    clientId: prev?.client_id ?? null,
    importance: prev?.importance ?? 3,
    tags: prev?.tags ?? [],
  });
  await sql(
    `UPDATE memory SET active = false, superseded_by = $2, updated_at = now()
      WHERE id = $1`,
    [oldId, replacement.id],
  );
  return replacement;
}

export async function forget(id: string): Promise<void> {
  await sql(`UPDATE memory SET active = false, updated_at = now() WHERE id = $1`, [id]);
}

async function touch(ids: string[]): Promise<void> {
  if (!ids.length) return;
  await sql(
    `UPDATE memory SET hit_count = hit_count + 1, last_used_at = now()
      WHERE id = ANY($1::uuid[])`,
    [ids],
  );
}

export async function memoryStats(): Promise<{
  total: number;
  byKind: { kind: string; n: number }[];
}> {
  const [{ n }] = await sql<{ n: string }>(
    `SELECT count(*)::int AS n FROM memory WHERE active = true`,
  );
  const byKind = await sql<{ kind: string; n: number }>(
    `SELECT kind, count(*)::int AS n FROM memory
      WHERE active = true GROUP BY kind ORDER BY n DESC`,
  );
  return { total: Number(n), byKind };
}
