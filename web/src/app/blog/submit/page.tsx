import type { Metadata } from "next";
import { ArticleSubmitForm } from "@/components/article-submit-form";
import { Breadcrumbs } from "@/components/ui/primitives";

export const metadata: Metadata = {
  title: "Write an article",
  robots: { index: false },
  alternates: { canonical: "/blog/submit" },
};

export default function Page() {
  return (
    <div className="mx-auto max-w-2xl space-y-4">
      <Breadcrumbs
        items={[
          { label: "Home", href: "/" },
          { label: "Articles", href: "/blog" },
          { label: "Write an article" },
        ]}
      />
      <h1 className="text-2xl font-semibold tracking-tight">Write an article</h1>
      <ArticleSubmitForm />
    </div>
  );
}
