import CardsApp from "@/components/cards/CardsApp";

export const metadata = { title: "Job cards · Shift Logger" };

export default function CardsPage() {
  return <CardsApp initialFilter="all" />;
}
