import CardReview from "@/components/cards/CardReview";

export const metadata = { title: "Job card · Shift Logger" };

export default async function CardPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CardReview id={id} />;
}
