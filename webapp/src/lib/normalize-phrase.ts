// Mirror of src/repositories/autopsy_repository.py:normalize_phrase, used as
// the AutopsyPanel "is this saved?" key. Python uses casefold(); JS lowercases
// with the es locale. Equivalent for Spanish Whisper output; if either side
// is ever fed other scripts (German ß, final sigma), the lookup will miss.
export function normalizePhrase(s: string): string {
	return s.trim().replace(/\s+/g, " ").toLocaleLowerCase("es");
}
