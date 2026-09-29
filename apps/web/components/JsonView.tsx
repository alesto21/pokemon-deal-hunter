export default function JsonView({ value }: { value: unknown }) {
  return (
    <pre className="max-h-96 overflow-auto rounded bg-zinc-50 p-3 text-xs leading-relaxed dark:bg-zinc-900">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}
