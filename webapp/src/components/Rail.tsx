import { useQuery } from "@tanstack/react-query";
import { Link, useRouterState } from "@tanstack/react-router";
import type { ComponentType, SVGProps } from "react";
import { listChunks, listVideos } from "../lib/api";
import {
	IconChunks,
	IconHome,
	IconLibrary,
	IconPlay,
	IconSearch,
	IconStats,
} from "./icons";

type IconComponent = ComponentType<SVGProps<SVGSVGElement>>;

type StaticStudyItem = {
	id: string;
	label: string;
	to: string;
	matchPrefix: string;
	icon: IconComponent;
	count?: number;
};

const HOME_ITEM: StaticStudyItem = {
	id: "home",
	label: "Inicio",
	to: "/",
	matchPrefix: "/",
	icon: IconHome,
};

const SEARCH_ITEM: StaticStudyItem = {
	id: "search",
	label: "Buscar",
	to: "/search",
	matchPrefix: "/search",
	icon: IconSearch,
};

const CHUNKS_ITEM: StaticStudyItem = {
	id: "chunks",
	label: "Mis frases",
	to: "/chunks",
	matchPrefix: "/chunks",
	icon: IconChunks,
};

function StaticNavLink({
	item,
	active,
}: {
	item: StaticStudyItem;
	active: boolean;
}) {
	const Ic = item.icon;
	return (
		<Link to={item.to} className={`nav-item ${active ? "is-active" : ""}`}>
			<span className="nav-icon">
				<Ic />
			</span>
			<span className="nav-label">{item.label}</span>
			{item.count !== undefined && (
				<span className="nav-count">{item.count}</span>
			)}
		</Link>
	);
}

export function Rail() {
	const pathname = useRouterState({ select: (s) => s.location.pathname });

	const isActive = (matchPrefix: string) =>
		matchPrefix === "/" ? pathname === "/" : pathname.startsWith(matchPrefix);

	// "Escuchando ahora" tracks the most recently processed video. Without a
	// per-user "last watched" signal (lands with 020), newest-first is the
	// closest stand-in. If no videos exist yet, the item is hidden rather than
	// linking to a non-existent id.
	const videosQuery = useQuery({
		queryKey: ["videos-list"],
		queryFn: listVideos,
	});
	const currentVideo = videosQuery.data?.videos[0];

	const chunksQuery = useQuery({
		queryKey: ["chunks"],
		queryFn: listChunks,
	});
	const chunksItem: StaticStudyItem = {
		...CHUNKS_ITEM,
		count: chunksQuery.data?.length ?? 0,
	};

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
				<StaticNavLink
					item={HOME_ITEM}
					active={isActive(HOME_ITEM.matchPrefix)}
				/>

				<StaticNavLink
					item={SEARCH_ITEM}
					active={isActive(SEARCH_ITEM.matchPrefix)}
				/>

				{currentVideo && (
					<Link
						to="/listen/$id"
						params={{ id: currentVideo.video_id }}
						className={`nav-item ${isActive("/listen") ? "is-active" : ""}`}
					>
						<span className="nav-icon">
							<IconPlay />
						</span>
						<span className="nav-label">Escuchando ahora</span>
						<span className="nav-subtle" title={currentVideo.title}>
							{currentVideo.title}
						</span>
					</Link>
				)}

				<StaticNavLink
					item={chunksItem}
					active={isActive(chunksItem.matchPrefix)}
				/>

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
