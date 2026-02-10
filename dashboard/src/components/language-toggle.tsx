"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

export function LanguageToggle() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const current = searchParams.get("lang") ?? "en";

  function handleChange(value: string) {
    if (!value) return; // Prevent deselection
    if (value === "en") {
      router.push("/sets");
    } else {
      router.push(`/sets?lang=${value}`);
    }
  }

  return (
    <ToggleGroup
      type="single"
      value={current}
      onValueChange={handleChange}
      variant="outline"
      size="sm"
    >
      <ToggleGroupItem value="en" className="text-xs px-3">
        English
      </ToggleGroupItem>
      <ToggleGroupItem value="ja" className="text-xs px-3">
        Japanese
      </ToggleGroupItem>
    </ToggleGroup>
  );
}
