/**
 * Org query helpers — keep route handlers thin.
 */
import { db } from "../index.js";

export async function loadOrgWithRelations(id: string) {
  const org = await db.org.findUnique({
    where: { id },
    include: {
      agents: {
        orderBy: { hiredAt: "asc" },
        select: { name: true, role: true, runtime: true, hiredAt: true },
      },
      members: {
        orderBy: { createdAt: "asc" },
        include: {
          user: { select: { email: true, name: true } },
        },
      },
    },
  });
  if (!org) return null;
  return {
    id: org.id,
    name: org.name,
    project: org.project,
    teamSize: org.teamSize,
    primaryClient: org.primaryClient,
    createdAt: org.createdAt.toISOString(),
    agents: org.agents.map((a) => ({
      name: a.name,
      role: a.role,
      runtime: a.runtime,
      hiredAt: a.hiredAt.toISOString(),
    })),
    members: org.members.map((m) => ({
      email: m.user.email,
      name: m.user.name,
      role: m.role,
      createdAt: m.createdAt.toISOString(),
    })),
  };
}

export type OrgWithRelations = NonNullable<Awaited<ReturnType<typeof loadOrgWithRelations>>>;
