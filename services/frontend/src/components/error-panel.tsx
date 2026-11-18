import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

/** What went wrong and what to do, in place of the content that couldn't load. */
export function ErrorPanel({ title, text }: { title: string; text: string }) {
  return (
    <Alert className="mt-4 rounded-md border-0 border-l-[6px] border-l-down bg-surface px-4 py-4 text-ink">
      <AlertTitle className="text-xl font-bold">{title}</AlertTitle>
      <AlertDescription className="mt-1 text-[15px] leading-snug text-ink/85">{text}</AlertDescription>
    </Alert>
  );
}
