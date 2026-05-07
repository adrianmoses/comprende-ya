import { useState } from "react";
import type { AutopsyEntry } from "../lib/autopsy-types";

type Props = {
	entry: AutopsyEntry;
	isSaved: boolean;
	onClose: () => void;
	onSave: () => void;
	onReplay: () => void;
};

type LayerKey = "grammar" | "register";

export function AutopsyPanel({
	entry,
	isSaved,
	onClose,
	onSave,
	onReplay,
}: Props) {
	const [openLayers, setOpenLayers] = useState<Record<LayerKey, boolean>>({
		grammar: true,
		register: true,
	});
	const toggle = (k: LayerKey) => setOpenLayers((s) => ({ ...s, [k]: !s[k] }));

	return (
		<div className="panel">
			<div className="panel-h">
				<h4>Phrase Autopsy</h4>
				<button
					type="button"
					className="panel-close"
					onClick={onClose}
					aria-label="Cerrar"
				>
					×
				</button>
			</div>
			<div className="panel-body autopsy-head">
				<h2 className="autopsy-phrase">«{entry.phrase}»</h2>
				<div className="autopsy-register">{entry.register}</div>
			</div>

			<Layer
				n={1}
				title="Gramática"
				open={openLayers.grammar}
				onToggle={() => toggle("grammar")}
			>
				{entry.grammar.map((g) => (
					<div key={g.tag} className="gram-row">
						<div className="gram-tag">{g.tag}</div>
						<div>{g.text}</div>
					</div>
				))}
			</Layer>

			<Layer
				n={2}
				title="Por qué suena natural"
				open={openLayers.register}
				onToggle={() => toggle("register")}
			>
				{entry.natural_notes.map((note) => (
					<div key={note} className="nat-row">
						— {note}
					</div>
				))}
			</Layer>

			<div className="autopsy-foot">
				<button
					type="button"
					className={isSaved ? "btn accent" : "btn"}
					onClick={onSave}
				>
					{isSaved ? "Guardada en biblioteca" : "Guardar en biblioteca"}
				</button>
				<button type="button" className="btn ghost sm" onClick={onReplay}>
					Re-escuchar
				</button>
			</div>
		</div>
	);
}

type LayerProps = {
	n: number;
	title: string;
	open: boolean;
	onToggle: () => void;
	children: React.ReactNode;
};

function Layer({ n, title, open, onToggle, children }: LayerProps) {
	return (
		<div className={`layer ${open ? "is-open" : ""}`}>
			<button
				type="button"
				className="layer-h"
				onClick={onToggle}
				aria-expanded={open}
			>
				<span className="layer-num">{n}</span>
				<span className="layer-title">{title}</span>
				<span className="layer-chev">›</span>
			</button>
			{open && <div className="layer-body">{children}</div>}
		</div>
	);
}
