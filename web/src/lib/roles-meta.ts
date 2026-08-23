/**
 * Human-friendly role metadata: plain-language descriptions and display
 * families so the taxonomy reads like job-market language, not machine codes.
 * Codes are stable identity; these labels are presentation-only.
 */

export type RoleFamily =
  | "Engineering"
  | "Data & AI"
  | "Product & Design"
  | "Go-to-market"
  | "Operations & Support"
  | "Specialist";

export interface RoleMeta {
  family: RoleFamily;
  description: string;
}

const ROLE_META: Record<string, RoleMeta> = {
  backend: {
    family: "Engineering",
    description:
      "Server-side engineering: APIs, business logic, databases and services.",
  },
  frontend: {
    family: "Engineering",
    description: "Interfaces users see and interact with in the browser.",
  },
  full_stack: {
    family: "Engineering",
    description: "Both server-side and browser-side development end to end.",
  },
  mobile: {
    family: "Engineering",
    description: "Apps for iOS and Android phones and tablets.",
  },
  devops_platform: {
    family: "Engineering",
    description:
      "Runs and scales software: cloud infrastructure, CI/CD, reliability.",
  },
  qa: {
    family: "Engineering",
    description: "Testing software so bugs never reach users.",
  },
  security: {
    family: "Specialist",
    description:
      "Protecting systems and data from attacks; investigating incidents.",
  },
  blockchain_protocol: {
    family: "Engineering",
    description:
      "Web3 engineering: smart contracts, protocols, on-chain systems.",
  },
  data: {
    family: "Data & AI",
    description:
      "Data pipelines, analytics and models that turn raw data into answers.",
  },
  ai_ml: {
    family: "Data & AI",
    description: "Building and shipping AI/ML features and models.",
  },
  product: {
    family: "Product & Design",
    description:
      "Decides what gets built and why; owns the product roadmap.",
  },
  design: {
    family: "Product & Design",
    description: "Designs how the product looks, feels and flows for users.",
  },
  sales_bd: {
    family: "Go-to-market",
    description:
      "Finds customers, sells the product and builds partnerships. (Some titles combine selling with technical work — that is why you may see DevOps-style skills here.)",
  },
  marketing_growth: {
    family: "Go-to-market",
    description:
      "Brings people to the product: campaigns, content, growth experiments.",
  },
  community: {
    family: "Go-to-market",
    description:
      "Talks with users and developers; runs communities, Discord, forums, events.",
  },
  support: {
    family: "Operations & Support",
    description:
      "Helps customers day to day: answering questions, solving problems, trust & safety.",
  },
  operations: {
    family: "Operations & Support",
    description: "Keeps the business running: processes, vendors, logistics.",
  },
  finance: {
    family: "Operations & Support",
    description:
      "Money matters: accounting, treasury, trading, financial analysis.",
  },
  legal_compliance: {
    family: "Specialist",
    description:
      "Contracts, regulation and compliance — including AML investigations.",
  },
};

const FAMILY_ORDER: RoleFamily[] = [
  "Engineering",
  "Data & AI",
  "Product & Design",
  "Go-to-market",
  "Operations & Support",
  "Specialist",
];

export function getRoleMeta(code: string): RoleMeta | null {
  return ROLE_META[code] ?? null;
}

export function groupRolesByFamily(
  roles: Array<{ code: string }>,
): Array<{ family: RoleFamily | "Other"; codes: string[] }> {
  const byFamily = new Map<RoleFamily | "Other", string[]>();
  for (const role of roles) {
    const meta = ROLE_META[role.code];
    // Roles missing from this presentation map must never disappear from the
    // page — they fall back to an explicit "Other" bucket until documented.
    const family: RoleFamily | "Other" = meta?.family ?? "Other";
    const bucket = byFamily.get(family) ?? [];
    bucket.push(role.code);
    byFamily.set(family, bucket);
  }
  return FAMILY_ORDER.filter((family) => byFamily.has(family)).map((family) => ({
    family,
    codes: byFamily.get(family) as string[],
  }));
}
