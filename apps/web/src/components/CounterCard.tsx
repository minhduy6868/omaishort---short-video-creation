type CounterCardProps = {
  label: string;
  value: number;
  hint?: string;
};

export function CounterCard({ label, value, hint }: CounterCardProps) {
  return (
    <article className="counter-card">
      <span>{label}</span>
      <strong>{value}</strong>
      {hint ? <small>{hint}</small> : null}
    </article>
  );
}
