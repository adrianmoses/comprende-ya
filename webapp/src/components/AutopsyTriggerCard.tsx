import type { AutopsyEntry } from "../lib/autopsy-types";

type Props = {
	entries: Array<AutopsyEntry>;
	savedPhrases: Set<string>;
	onPick: (entry: AutopsyEntry) => void;
};

export function AutopsyTriggerCard({ entries, savedPhrases, onPick }: Props) {
	if (!entries.length) return null;
	return (
		<div className="panel">
			<div className="panel-h">
				<h4>Frases destacadas</h4>
				<span className="panel-tag">temporal · ver 018</span>
			</div>
			<div className="autopsy-list">
				{entries.map((entry) => {
					const cls = savedPhrases.has(entry.phrase)
						? "autopsy-list-row is-saved"
						: "autopsy-list-row";
					return (
						<button
							key={entry.phrase}
							type="button"
							className={cls}
							onClick={() => onPick(entry)}
						>
							<span className="autopsy-list-phrase">«{entry.phrase}»</span>
							<span className="autopsy-list-register">{entry.register}</span>
						</button>
					);
				})}
			</div>
		</div>
	);
}
