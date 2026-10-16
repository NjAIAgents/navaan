import { useCallback, useEffect, useState } from "react";
import { applyChoice, readChoice, saveChoice, type Choice } from "./themes";

export function useTheme() {
  const [choice, setChoiceState] = useState<Choice>(() => readChoice());
  const setChoice = useCallback((c: Choice) => { saveChoice(c); applyChoice(c); setChoiceState(c); }, []);
  useEffect(() => {
    if (choice !== "system" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-color-scheme: light)");
    const follow = () => applyChoice("system");
    mq.addEventListener("change", follow);
    return () => mq.removeEventListener("change", follow);
  }, [choice]);
  return { choice, setChoice };
}
