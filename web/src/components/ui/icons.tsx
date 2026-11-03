import {
  Activity,
  BookOpen,
  Bird,
  BriefcaseBusiness,
  Building2,
  Calculator,
  Cat,
  ClipboardCheck,
  Dog,
  Factory,
  FileText,
  Flag,
  FlaskConical,
  GraduationCap,
  Home,
  Landmark,
  Layers,
  Library,
  MessageSquareText,
  PawPrint,
  Pill,
  Search,
  ShieldCheck,
  Stethoscope,
  Syringe,
  type LucideIcon,
} from "lucide-react";

export type Tone = "teal" | "blue" | "green" | "violet" | "amber" | "red";

/** One semantic icon per content area, so a category looks the same wherever it appears. */
export const CATEGORIES = {
  home: { icon: Home, tone: "teal" },
  medicines: { icon: Pill, tone: "teal" },
  vaccines: { icon: Syringe, tone: "teal" },
  diseases: { icon: Activity, tone: "red" },
  species: { icon: PawPrint, tone: "green" },
  calculators: { icon: Calculator, tone: "violet" },
  universities: { icon: Building2, tone: "blue" },
  scholarships: { icon: GraduationCap, tone: "blue" },
  jobs: { icon: BriefcaseBusiness, tone: "blue" },
  papers: { icon: FileText, tone: "blue" },
  mocktests: { icon: ClipboardCheck, tone: "blue" },
  study: { icon: BookOpen, tone: "blue" },
  lessons: { icon: Library, tone: "blue" },
  countries: { icon: Flag, tone: "green" },
  companies: { icon: Factory, tone: "teal" },
  regulatory: { icon: Landmark, tone: "teal" },
  search: { icon: Search, tone: "teal" },
  reference: { icon: Stethoscope, tone: "teal" },
  classes: { icon: Layers, tone: "teal" },
  interactions: { icon: FlaskConical, tone: "red" },
  ask: { icon: MessageSquareText, tone: "teal" },
  verified: { icon: ShieldCheck, tone: "green" },
} as const satisfies Record<string, { icon: LucideIcon; tone: Tone }>;

export type CategoryName = keyof typeof CATEGORIES;

const SIZES = {
  sm: ["h-8 w-8 rounded-md", 16],
  md: ["h-10 w-10 rounded-lg", 20],
  lg: ["h-12 w-12 rounded-xl", 24],
} as const;

/** Decorative icon in a tinted chip. Always `aria-hidden`: the adjacent text carries the meaning. */
export function IconChip({
  category,
  icon,
  tone,
  size = "md",
}: {
  category?: CategoryName;
  icon?: LucideIcon;
  tone?: Tone;
  size?: keyof typeof SIZES;
}) {
  const def = category ? CATEGORIES[category] : undefined;
  const Icon = icon ?? def?.icon ?? PawPrint;
  const [cls, px] = SIZES[size];
  return (
    <span className={`icon-chip tone-${tone ?? def?.tone ?? "teal"} ${cls}`} aria-hidden="true">
      <Icon size={px} strokeWidth={1.75} />
    </span>
  );
}

/** Bare category glyph for inline use next to text. */
export function CategoryIcon({
  category,
  size = 18,
  className,
}: {
  category: CategoryName;
  size?: number;
  className?: string;
}) {
  const Icon = CATEGORIES[category].icon;
  return <Icon size={size} strokeWidth={1.75} aria-hidden="true" className={className} />;
}

/** Species glyph by slug or name; the generic paw is the fallback so nothing is mislabelled. */
export function speciesIcon(slugOrName: string): LucideIcon {
  const k = slugOrName.toLowerCase();
  if (/\b(dog|canine)s?\b/.test(k)) return Dog;
  if (/\b(cat|feline)s?\b/.test(k)) return Cat;
  if (/(poultry|chicken|bird|avian|duck|turkey|hen)/.test(k)) return Bird;
  return PawPrint;
}
