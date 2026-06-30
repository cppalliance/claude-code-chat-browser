/** Backend tool-use names from ``static/tool_types.json`` (set at SPA init). */

let manifestToolTypes = null;

export function setManifestToolTypes(types) {
    manifestToolTypes = types;
}

export function getManifestToolTypes() {
    return manifestToolTypes;
}

export function isManifestToolType(name) {
    return manifestToolTypes !== null && manifestToolTypes.has(name);
}
