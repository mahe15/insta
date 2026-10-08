import type { Preferences } from "./types";
import { Field } from "./ui";

export type Rules = Pick<Preferences, "project_rules" | "description_suffix" | "overlay_text">;
export const emptyRules: Rules = { project_rules: "", description_suffix: "", overlay_text: "" };

export default function ProjectRules({ value, onChange, discovered = false }: {
  value: Rules; onChange: (value: Rules) => void; discovered?: boolean;
}) {
  return <section className="project-rules">
    <h3>Project rules</h3>
    <p className="muted">Only this project. Applied to every clip.</p>
    <Field label="AI editing instructions" hint={discovered
      ? "Used during discovery. Create a new project to change the selection instructions."
      : "Guide the AI’s selection, hooks and descriptions. Offline ranking cannot follow creative instructions."}>
      <textarea rows={3} maxLength={2000} readOnly={discovered}
        value={value.project_rules || ""}
        placeholder="Focus on football reactions. Keep hooks short and playful. Avoid spoilers."
        onChange={e => onChange({ ...value, project_rules: e.target.value })} />
    </Field>
    <Field label="Always include in post description" hint="Added automatically to every publishing caption. Required hashtags take priority (maximum five).">
      <textarea rows={2} maxLength={500} value={value.description_suffix || ""}
        placeholder="Follow for more. #done"
        onChange={e => onChange({ ...value, description_suffix: e.target.value })} />
    </Field>
    <Field label="Always show on the video" hint="A separate text label throughout every clip, below the picture in square layout. It does not alter spoken subtitles.">
      <input maxLength={80} value={value.overlay_text || ""} placeholder="#done · @yourpage"
        onChange={e => onChange({ ...value, overlay_text: e.target.value })} />
    </Field>
  </section>;
}
