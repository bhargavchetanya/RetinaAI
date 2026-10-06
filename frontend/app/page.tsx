import Link from "next/link";

const PIPELINE = [
  { step: "01", title: "Data collection", text: "APTOS-2019 (Aravind Eye Hospital, India) via the Kaggle API – 3,662 graded fundus photos." },
  { step: "02", title: "Pre-processing", text: "Crop black border, Ben Graham contrast filter, de-duplication, stratified 70/15/15 split." },
  { step: "03", title: "Transfer learning", text: "EfficientNet-B0 pre-trained on ImageNet, fine-tuned with class-weighted loss on Apple MPS." },
  { step: "04", title: "Trust layer", text: "Temperature-scaled confidence, quality check and K-NN out-of-distribution guard." },
  { step: "05", title: "Explainability", text: "Grad-CAM++ heat-map + plain-language explanation of what the model saw." },
  { step: "06", title: "Referral", text: "Referable DR (grade ≥ 2) threshold tuned for ≥ 90 % sensitivity, PDF report, dashboard." },
  { step: "07", title: "Secure access", text: "Patient, doctor, hospital and admin logins – everyone sees only the records they are allowed to." },
  { step: "08", title: "Assistant", text: "Offline TF-IDF chatbot answers questions about DR, results and the app (bottom-right)." },
  { step: "09", title: "Offline-ready", text: "Runs on a laptop without internet; ONNX export for cheap CPU devices." },
];

export default function Home() {
  return (
    <main className="text-white">
      <section className="mx-auto flex max-w-7xl flex-col px-4 py-16 sm:px-6 sm:py-20">
        <div className="max-w-4xl">
          <div className="mb-6 inline-block rounded-full border border-cyan-500/30 bg-cyan-500/10 px-4 py-2 text-sm text-cyan-400">
            Explainable AI • Computer Vision • Transfer Learning
          </div>

          <h1 className="text-4xl font-bold leading-tight sm:text-5xl md:text-7xl">
            <span className="text-cyan-400">RetinaAI</span>
            <br />
            Explainable Diabetic Retinopathy Screening
          </h1>

          <p className="mt-6 max-w-3xl text-lg leading-8 text-slate-400">
            A low-cost screening assistant for primary health centres. A health worker uploads a retinal (fundus)
            photo and gets a severity grade, an honest confidence score, a heat-map of what the model looked at and a
            referral recommendation.
          </p>

          <div className="mt-10 flex flex-col gap-4 sm:flex-row">
            <Link href="/login" className="rounded-xl bg-cyan-500 px-6 py-3 text-center font-semibold text-slate-950 hover:bg-cyan-400">
              Log in
            </Link>
            <Link href="/register" className="rounded-xl border border-slate-700 px-6 py-3 text-center font-semibold hover:bg-slate-900">
              Register as patient
            </Link>
            <Link href="/model" className="rounded-xl border border-slate-700 px-6 py-3 text-center font-semibold hover:bg-slate-900">
              How the model performs
            </Link>
          </div>
        </div>

        <div className="mt-16 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
          <FeatureCard value="5" title="DR grades" description="No DR → Proliferative DR (ICDR scale)" />
          <FeatureCard value="B0" title="EfficientNet" description="≈4 M parameters – runs on a laptop CPU" />
          <FeatureCard value="XAI" title="Grad-CAM++" description="Implemented from scratch with PyTorch hooks" />
          <FeatureCard value="MPS" title="Apple GPU" description="Trained locally on Apple Silicon" />
        </div>

        <h2 className="mt-16 text-2xl font-semibold">Pipeline</h2>
        <div className="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {PIPELINE.map((p) => (
            <div key={p.step} className="rounded-2xl border border-slate-800 bg-slate-900 p-5">
              <div className="text-sm font-semibold text-cyan-400">{p.step}</div>
              <h3 className="mt-1 font-semibold">{p.title}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-400">{p.text}</p>
            </div>
          ))}
        </div>

      </section>
    </main>
  );
}

function FeatureCard({ value, title, description }: { value: string; title: string; description: string }) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
      <div className="text-3xl font-bold text-cyan-400">{value}</div>
      <h3 className="mt-3 font-semibold">{title}</h3>
      <p className="mt-2 text-sm text-slate-500">{description}</p>
    </div>
  );
}
