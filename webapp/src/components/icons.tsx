import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

type IconOptions = {
	fill?: string;
	strokeWidth?: number;
};

function makeIcon(content: React.ReactNode, opts: IconOptions = {}) {
	const Icon = ({ className, style, ...rest }: IconProps) => (
		<svg
			className={`icon ${className ?? ""}`.trim()}
			viewBox="0 0 24 24"
			fill={opts.fill ?? "none"}
			stroke="currentColor"
			strokeWidth={opts.strokeWidth ?? 1.5}
			strokeLinecap="round"
			strokeLinejoin="round"
			style={style}
			aria-hidden="true"
			{...rest}
		>
			{content}
		</svg>
	);
	return Icon;
}

export const IconHome = makeIcon(
	<path d="M4 11.5 12 5l8 6.5V19a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1z" />,
);

export const IconLibrary = makeIcon(
	<>
		<rect x="4" y="5" width="4" height="14" rx="1" />
		<rect x="10" y="5" width="4" height="14" rx="1" />
		<path d="m17 6 3 .8-2.5 12.6L14.5 18.6z" />
	</>,
);

export const IconChunks = makeIcon(
	<>
		<rect x="4" y="4" width="7" height="7" rx="1" />
		<rect x="13" y="4" width="7" height="7" rx="1" />
		<rect x="4" y="13" width="7" height="7" rx="1" />
		<rect x="13" y="13" width="7" height="7" rx="1" />
	</>,
);

export const IconStats = makeIcon(
	<>
		<path d="M4 19V5" />
		<path d="m4 19 5-5 4 3 7-8" />
	</>,
);

export const IconSettings = makeIcon(
	<>
		<circle cx="12" cy="12" r="3" />
		<path d="M12 3v2m0 14v2M5 12H3m18 0h-2m-2.5-6.5L18 4m-12 16 1.5-1.5M18 20l-1.5-1.5M6 6 4.5 4.5" />
	</>,
);

export const IconPlay = makeIcon(<path d="M7 5v14l12-7z" />, {
	fill: "currentColor",
	strokeWidth: 0,
});

export const IconSearch = makeIcon(
	<>
		<circle cx="11" cy="11" r="6" />
		<path d="m20 20-4.5-4.5" />
	</>,
);

export const IconBookmarkFilled = makeIcon(<path d="M6 4h12v17l-6-4-6 4z" />, {
	fill: "currentColor",
});
