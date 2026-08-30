export default function Toast({ message }: { message: string }) {
  return (
    <div className="fixed right-5 top-20 z-[60] rounded-lg bg-[#07111f]/95 px-4 py-3 text-sm font-semibold text-white shadow-[0_18px_40px_rgba(0,0,0,0.35),0_0_20px_rgba(99,102,241,0.16)] backdrop-blur-xl">
      {message}
    </div>
  );
}
