import { Link, useRouterState } from "@tanstack/react-router";
import { Fragment } from "react";
import { IconSearch, IconSettings } from "./icons";

type Crumb = { label: string; to?: string };

function crumbsForPath(pathname: string): Array<Crumb> {
	if (pathname.startsWith("/listen")) {
		return [{ label: "Inicio", to: "/" }, { label: "Escuchando" }];
	}
	if (pathname.startsWith("/chunks")) {
		return [{ label: "Mis frases" }];
	}
	return [{ label: "Inicio" }];
}

export function TopBar() {
	const pathname = useRouterState({ select: (s) => s.location.pathname });
	const crumbs = crumbsForPath(pathname);
	const last = crumbs.length - 1;

	return (
		<div className="topbar">
			<div className="crumbs">
				{crumbs.map((c, i) => {
					const isLast = i === last;
					return (
						<Fragment key={c.label}>
							{isLast ? (
								<b>{c.label}</b>
							) : c.to ? (
								<Link to={c.to}>{c.label}</Link>
							) : (
								<span>{c.label}</span>
							)}
							{!isLast && <span className="sep"> › </span>}
						</Fragment>
					);
				})}
			</div>
			<div className="top-actions">
				<button type="button" className="btn ghost sm btn--muted">
					<IconSearch /> Buscar episodios
				</button>
				<button type="button" className="btn ghost sm">
					<IconSettings />
				</button>
			</div>
		</div>
	);
}
