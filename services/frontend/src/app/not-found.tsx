import Link from "next/link";

export default function NotFound() {
  return (
    <>
      <h1 className="mt-6 text-[22px] font-bold">No plot with this id.</h1>
      <Link href="/" className="mt-2 inline-block text-water underline-offset-2 hover:underline">
        All farms
      </Link>
    </>
  );
}
