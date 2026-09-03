(() => {
    if (typeof window === "undefined" || typeof window.tailwind === "undefined") return;

    const currentConfig = window.tailwind.config || {};
    const theme = currentConfig.theme || {};
    const extend = theme.extend || {};
    const fontFamily = extend.fontFamily || {};
    const colors = extend.colors || {};
    const indigo = colors.indigo || {};
    const slate = colors.slate || {};

    window.tailwind.config = {
        ...currentConfig,
        theme: {
            ...theme,
            extend: {
                ...extend,
                fontFamily: {
                    sans: ["Outfit", "sans-serif"],
                    mono: ["JetBrains Mono", "monospace"],
                    ...fontFamily
                },
                colors: {
                    ...colors,
                    indigo: {
                        50: "#eef2ff",
                        400: "#818cf8",
                        500: "#6366f1",
                        600: "#4f46e5",
                        900: "#312e81",
                        ...indigo
                    },
                    slate: {
                        850: "#1e293b",
                        900: "#0f172a",
                        950: "#020617",
                        ...slate
                    }
                }
            }
        }
    };
})();
