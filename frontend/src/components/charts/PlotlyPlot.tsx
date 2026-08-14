// react-plotly.js is a CommonJS package built with `exports.default = Component`.
// Depending on how esbuild/Vite's dependency pre-bundler wraps the CJS→ESM
// interop, `import Plot from "react-plotly.js"` can resolve to the *whole*
// exports object (`{ default: Component }`) instead of the component itself,
// which throws "Element type is invalid" at render time. Unwrap defensively
// (recursively, since the exact nesting depends on the bundler) so every
// chart in the app imports a guaranteed-correct component from here instead
// of importing "react-plotly.js" directly.
import PlotlyImport from "react-plotly.js";

type PlotComponentType = typeof import("react-plotly.js").default;

function unwrap(mod: unknown): PlotComponentType {
  if (typeof mod === "function") return mod as PlotComponentType;
  if (mod && typeof mod === "object" && "default" in mod) {
    return unwrap((mod as { default: unknown }).default);
  }
  throw new Error("react-plotly.js: could not resolve the Plot component export");
}

const Plot: PlotComponentType = unwrap(PlotlyImport);
export default Plot;
