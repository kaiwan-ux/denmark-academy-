export type MockQualityQuestion = {
  stem: string;
  learning_objective?: string;
  context_key?: string;
  choices?: { text: string }[];
};

export class MockSelectionGuard {
  private readonly stems: string[] = [];
  private readonly objectives: string[] = [];
  private readonly contexts = new Set<string>();

  canAccept(question: MockQualityQuestion, enforceObjective = true): boolean {
    const stem = normalizeSemantic(question.stem);
    if (!stem || !plausibleChoices(question)) return false;
    if (this.stems.some((prior) => similarity(stem, prior) >= 0.85)) return false;

    const objective = normalizeSemantic(question.learning_objective || inferObjective(question.stem));
    if (enforceObjective && objective && this.objectives.some((prior) => similarity(objective, prior) >= 0.82)) {
      return false;
    }
    const context = normalizeSemantic(question.context_key || "");
    if (enforceObjective && context && this.contexts.has(context)) return false;
    return true;
  }

  add(question: MockQualityQuestion): void {
    const stem = normalizeSemantic(question.stem);
    const objective = normalizeSemantic(question.learning_objective || inferObjective(question.stem));
    const context = normalizeSemantic(question.context_key || "");
    if (stem) this.stems.push(stem);
    if (objective) this.objectives.push(objective);
    if (context) this.contexts.add(context);
  }

  addReference(stem: string, objective = ""): void {
    const normalizedStem = normalizeSemantic(stem);
    const normalizedObjective = normalizeSemantic(objective);
    if (normalizedStem) this.stems.push(normalizedStem);
    if (normalizedObjective) this.objectives.push(normalizedObjective);
  }
}

export function inferObjective(value: string): string {
  const normalized = normalizeSemantic(value);
  const groups: [string, string[]][] = [
    ["democracy institutions", ["folketing", "regering", "minister", "valg", "demokrati"]],
    ["constitution rights", ["grundlov", "rettighed", "ytringsfrihed", "religionsfrihed"]],
    ["history monarchy", ["konge", "dronning", "monarki", "histor", "krig"]],
    ["welfare health", ["velfærd", "sundhed", "hospital", "kommune"]],
    ["work education", ["arbejde", "uddannelse", "skole", "arbejdsmarked"]],
    ["culture society", ["kultur", "tradition", "religion", "samfund"]],
    ["current politics", ["aktuel", "aftale", "lovforslag", "reform"]],
  ];
  const match = groups.find(([, words]) => words.some((word) => normalized.includes(word)));
  if (match) return `${match[0]} ${significantWords(normalized).slice(0, 3).join(" ")}`;
  return significantWords(normalized).slice(0, 6).join(" ");
}

export function similarity(left: string, right: string): number {
  const a = normalizeSemantic(left);
  const b = normalizeSemantic(right);
  if (!a || !b) return 0;
  const leftWords = new Set(a.split(" "));
  const rightWords = new Set(b.split(" "));
  const intersection = [...leftWords].filter((word) => rightWords.has(word)).length;
  const jaccard = intersection / Math.max(1, new Set([...leftWords, ...rightWords]).size);
  return Math.max(jaccard, cosine(embed(a), embed(b)));
}

function plausibleChoices(question: MockQualityQuestion): boolean {
  if (!question.choices) return true;
  if (question.choices.length < 3) return false;
  const choices = question.choices.map((choice) => normalizeSemantic(choice.text));
  if (new Set(choices).size !== choices.length || choices.some((choice) => !choice)) return false;
  const lengths = choices.map((choice) => Math.max(1, choice.split(" ").length));
  return Math.max(...lengths) <= Math.max(5, Math.min(...lengths) * 3);
}

function normalizeSemantic(value: string): string {
  const aliases: Record<string, string> = {
    lovforslag: "lov", lovforslaget: "lov", lovgivning: "lov",
    vedtages: "vedtag", vedtaget: "vedtag", vedtage: "vedtag",
    folketinget: "folketing", regeringen: "regering",
    parlamentarismen: "parlamentarisme", parlamentarismens: "parlamentarisme",
    negative: "negativ", negativt: "negativ",
  };
  const stop = new Set(["af", "at", "den", "det", "der", "en", "et", "for", "fra", "har", "hvad", "hvem", "hvilken", "hvilket", "hvordan", "i", "med", "og", "på", "som", "til", "bliver", "blev", "er", "mellem", "fungerer", "følger", "sammenhæng"]);
  return value.toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9æøå]+/gi, " ").trim().split(/\s+/)
    .map((word) => aliases[word] || word).filter((word) => word && !stop.has(word)).join(" ");
}

function significantWords(value: string): string[] {
  return normalizeSemantic(value).split(" ").filter((word) => word.length > 3);
}

function embed(value: string): number[] {
  const vector = Array<number>(192).fill(0);
  const words = value.split(" ");
  const features = [...words, ...words.slice(0, -1).map((word, index) => `${word}_${words[index + 1]}`)];
  for (const feature of features) {
    let hash = 2166136261;
    for (let index = 0; index < feature.length; index += 1) {
      hash ^= feature.charCodeAt(index);
      hash = Math.imul(hash, 16777619);
    }
    vector[Math.abs(hash) % vector.length] += 1;
  }
  const norm = Math.sqrt(vector.reduce((sum, valueAtIndex) => sum + valueAtIndex ** 2, 0)) || 1;
  return vector.map((valueAtIndex) => valueAtIndex / norm);
}

function cosine(left: number[], right: number[]): number {
  return left.reduce((sum, value, index) => sum + value * right[index], 0);
}
