export default function JsonView({ value }: { value: unknown }) {
  return (
    <pre className="max-h-96 overflow-auto rounded-lg bg-surface-2 p-3 font-mono text-xs leading-relaxed text-ink-2">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
