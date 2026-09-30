export interface Subject {
  slug: string;
  name: string;
  topics: { slug: string; name: string }[];
}

export interface ExamQuestion {
  id: number;
  stem: string;
  topic: string;
  subject: string;
  difficulty: string;
  options: { id: number; label: string; text: string }[];
  // Present only after submission:
  correct_option?: number | null;
  explanation?: string;
  selected?: number | null;
  is_correct?: boolean;
}

export interface ExamDetail {
  id: number;
  submitted: boolean;
  score: number | null;
  questions: ExamQuestion[];
}

export interface HistoryRow {
  id: number;
  date: string;
  score: number;
  total: number;
}

export interface PastPaper {
  university: string;
  degree: string;
  course: string;
  year: number;
  semester: string;
  exam_type: string;
  url: string;
  license_note: string;
}
