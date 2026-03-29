const DEFAULT_CHECKPOINT_INTERVAL = 25;
const DEFAULT_MAX_RECENT_SNAPSHOTS = 24;

function cloneValue(value) {
    if (typeof structuredClone === 'function') {
        try {
            return structuredClone(value);
        } catch (error) {
        }
    }

    try {
        return JSON.parse(JSON.stringify(value));
    } catch (error) {
        return value;
    }
}

function isPlainObject(value) {
    return Object.prototype.toString.call(value) === '[object Object]';
}

function assignDefined(target, source) {
    if (!isPlainObject(target)) {
        return isPlainObject(source) ? cloneValue(source) : {};
    }
    if (!isPlainObject(source)) {
        return target;
    }

    Object.entries(source).forEach(([key, value]) => {
        target[key] = cloneValue(value);
    });
    return target;
}

export function normalizeMessageVariableEntries(message) {
    const source = message && typeof message === 'object' ? message : {};
    const rawVariables = source.variables;
    if (Array.isArray(rawVariables)) {
        return rawVariables.filter(entry => entry && typeof entry === 'object');
    }
    if (rawVariables && typeof rawVariables === 'object') {
        return [rawVariables];
    }
    return [];
}

export function getActiveMessageVariables(message) {
    const entries = normalizeMessageVariableEntries(message);
    if (!entries.length) return {};

    const swipeId = Number.isInteger(Number(message?.swipe_id)) ? Number(message.swipe_id) : 0;
    if (swipeId >= 0 && swipeId < entries.length && entries[swipeId] && typeof entries[swipeId] === 'object') {
        return cloneValue(entries[swipeId]);
    }

    return cloneValue(entries[0] || {});
}

export function getChatMetadataVariables(metadata) {
    const root = metadata && typeof metadata === 'object' ? metadata : {};
    const chatMetadata = root.chat_metadata && typeof root.chat_metadata === 'object' ? root.chat_metadata : {};
    const variables = chatMetadata.variables;
    return variables && typeof variables === 'object' && !Array.isArray(variables) ? cloneValue(variables) : {};
}

export function getCardVariables(cardDetail) {
    const source = cardDetail?.card && typeof cardDetail.card === 'object' ? cardDetail.card : cardDetail;
    const extensions = source?.extensions && typeof source.extensions === 'object' ? source.extensions : {};
    const helper = extensions?.tavern_helper && typeof extensions.tavern_helper === 'object' && !Array.isArray(extensions.tavern_helper)
        ? extensions.tavern_helper
        : {};
    const variables = helper.variables;
    return variables && typeof variables === 'object' && !Array.isArray(variables) ? cloneValue(variables) : {};
}

export function buildMessageVariableSignature(rawMessages) {
    const list = Array.isArray(rawMessages) ? rawMessages : [];
    return list.map((message, index) => {
        const entries = normalizeMessageVariableEntries(message);
        const swipeId = Number.isInteger(Number(message?.swipe_id)) ? Number(message.swipe_id) : 0;
        return `${index + 1}:${swipeId}:${entries.length}`;
    }).join('|');
}

function createRevisionKey({ chatId = '', rawMessages = [], metadata = null, cardDetail = null }) {
    const metadataVariables = JSON.stringify(getChatMetadataVariables(metadata));
    const cardVariables = JSON.stringify(getCardVariables(cardDetail));
    return [
        String(chatId || ''),
        String(Array.isArray(rawMessages) ? rawMessages.length : 0),
        buildMessageVariableSignature(rawMessages),
        metadataVariables,
        cardVariables,
    ].join('::');
}

export function computeFloorVariableSnapshot(rawMessages, floor, options = {}) {
    const list = Array.isArray(rawMessages) ? rawMessages : [];
    const targetFloor = Math.min(list.length, Math.max(0, Number(floor || 0)));
    const result = {};

    assignDefined(result, options.globalVariables);
    assignDefined(result, options.characterVariables || getCardVariables(options.cardDetail));
    assignDefined(result, options.chatVariables || getChatMetadataVariables(options.metadata));

    for (let index = 0; index < targetFloor; index += 1) {
        assignDefined(result, getActiveMessageVariables(list[index]));
    }

    return result;
}

export function createFloorVariableSnapshotResolver(options = {}) {
    const checkpointInterval = Math.max(1, Number(options.checkpointInterval) || DEFAULT_CHECKPOINT_INTERVAL);
    const maxRecentSnapshots = Math.max(1, Number(options.maxRecentSnapshots) || DEFAULT_MAX_RECENT_SNAPSHOTS);
    const state = {
        revisionKey: '',
        checkpoints: new Map(),
        recentSnapshots: new Map(),
    };

    function clearCaches(nextRevisionKey) {
        state.revisionKey = String(nextRevisionKey || '');
        state.checkpoints.clear();
        state.recentSnapshots.clear();
    }

    function touchRecentSnapshot(floor, snapshot) {
        const key = Number(floor || 0);
        state.recentSnapshots.delete(key);
        state.recentSnapshots.set(key, cloneValue(snapshot));
        while (state.recentSnapshots.size > maxRecentSnapshots) {
            const oldestKey = state.recentSnapshots.keys().next().value;
            state.recentSnapshots.delete(oldestKey);
        }
    }

    function resolveBaseSnapshot(targetFloor) {
        if (state.recentSnapshots.has(targetFloor)) {
            const cached = state.recentSnapshots.get(targetFloor);
            touchRecentSnapshot(targetFloor, cached);
            return { floor: targetFloor, snapshot: cloneValue(cached) };
        }

        let bestFloor = 0;
        let bestSnapshot = null;
        state.checkpoints.forEach((snapshot, floor) => {
            if (floor <= targetFloor && floor >= bestFloor) {
                bestFloor = floor;
                bestSnapshot = snapshot;
            }
        });

        if (bestSnapshot) {
            return { floor: bestFloor, snapshot: cloneValue(bestSnapshot) };
        }

        return { floor: 0, snapshot: null };
    }

    return {
        resolve({ chatId = '', rawMessages = [], floor = 0, metadata = null, cardDetail = null, globalVariables = {} } = {}) {
            const revisionKey = createRevisionKey({ chatId, rawMessages, metadata, cardDetail });
            if (revisionKey !== state.revisionKey) {
                clearCaches(revisionKey);
            }

            const list = Array.isArray(rawMessages) ? rawMessages : [];
            const targetFloor = Math.min(list.length, Math.max(0, Number(floor || 0)));
            if (targetFloor <= 0) {
                const emptySnapshot = computeFloorVariableSnapshot([], 0, {
                    metadata,
                    cardDetail,
                    globalVariables,
                });
                touchRecentSnapshot(0, emptySnapshot);
                return emptySnapshot;
            }

            if (state.recentSnapshots.has(targetFloor)) {
                const cached = state.recentSnapshots.get(targetFloor);
                touchRecentSnapshot(targetFloor, cached);
                return cloneValue(cached);
            }

            const base = resolveBaseSnapshot(targetFloor);
            const snapshot = base.snapshot || computeFloorVariableSnapshot([], 0, {
                metadata,
                cardDetail,
                globalVariables,
            });

            for (let index = base.floor; index < targetFloor; index += 1) {
                assignDefined(snapshot, getActiveMessageVariables(list[index]));
                const currentFloor = index + 1;
                if (currentFloor % checkpointInterval === 0) {
                    state.checkpoints.set(currentFloor, cloneValue(snapshot));
                }
            }

            touchRecentSnapshot(targetFloor, snapshot);
            return cloneValue(snapshot);
        },
        clear() {
            clearCaches('');
        },
    };
}
