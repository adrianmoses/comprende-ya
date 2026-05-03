import { Link, useRouterState } from "@tanstack/react-router";
import type { ComponentType, SVGProps } from "react";
import {
	IconChunks,
	IconHome,
	IconLibrary,
	IconPlay,
	IconStats,
} from "./icons";

type IconComponent = ComponentType<SVGProps<SVGSVGElement>>;

type StudyItem = {
	id: string;
	label: string;
	to: string;
	matchPrefix: string;
	icon: IconComponent;
	subtle?: string;
	count?: number;
};

const STUDY_ITEMS: ReadonlyArray<StudyItem> = [
	{
		id: "home",
		label: "Inicio",
		to: "/",
		matchPrefix: "/",
		icon: IconHome,
	},
	{
		id: "listen",
		label: "Escuchando ahora",
		to: "/listen/mercados",
		matchPrefix: "/listen",
		icon: IconPlay,
		subtle: "Mercados de barrio",
	},
	{
		id: "chunks",
		label: "Mis frases",
		to: "/chunks",
		matchPrefix: "/chunks",
		icon: IconChunks,
		// Real count comes with feature 020 (Mis frases / chunk library).
		count: 0,
	},
];

export function Rail() {
	const pathname = useRouterState({ select: (s) => s.location.pathname });

	const isActive = (matchPrefix: string) =>
		matchPrefix === "/" ? pathname === "/" : pathname.startsWith(matchPrefix);

	return (
		<aside className="rail">
			<div className="brand">
				<div className="brand-mark">C</div>
				<div className="brand-name">
					Comprende <em>Ya</em>
				</div>
			</div>

			<div className="nav">
				<div className="nav-section">Estudio</div>
				{STUDY_ITEMS.map((it) => {
					const Ic = it.icon;
					const active = isActive(it.matchPrefix);
					return (
						<Link
							key={it.id}
							to={it.to}
							className={`nav-item ${active ? "is-active" : ""}`}
						>
							<span className="nav-icon">
								<Ic />
							</span>
							<span className="nav-label">{it.label}</span>
							{it.count !== undefined && (
								<span className="nav-count">{it.count}</span>
							)}
							{it.subtle !== undefined && (
								<span className="nav-subtle">{it.subtle}</span>
							)}
						</Link>
					);
				})}

				<div className="nav-section">Biblioteca</div>
				<button type="button" className="nav-item">
					<span className="nav-icon">
						<IconLibrary />
					</span>
					<span>Episodios</span>
				</button>
				<button type="button" className="nav-item">
					<span className="nav-icon">
						<IconStats />
					</span>
					<span>Progreso</span>
				</button>
			</div>

			<div className="rail-foot">
				<div className="avatar">A</div>
				<div>
					<div className="rail-foot-name">Ana · B2</div>
					<div className="rail-foot-meta">Día 6 de la racha</div>
				</div>
			</div>
		</aside>
	);
}
