function sanitizeRegexMacroValue(value) {
  return String(value ?? "").replaceAll(
    /[\n\r\t\v\f\0.^$*+?{}[\]\\/|()]/gs,
    (token) => {
      switch (token) {
        case "\n":
          return "\\n";
        case "\r":
          return "\\r";
        case "\t":
          return "\\t";
        case "\v":
          return "\\v";
        case "\f":
          return "\\f";
        case "\0":
          return "\\0";
        default:
          return `\\${token}`;
      }
    },
  );
}

function substituteRegexTestBenchMacros(
  text,
  macroContext = {},
  sanitizer = null,
) {
  const source = String(text ?? "");
  const context =
    macroContext && typeof macroContext === "object" ? macroContext : {};

  return source.replace(/\{\{\s*([^{}]+?)\s*\}\}/g, (match, rawKey) => {
    const key = String(rawKey || "")
      .trim()
      .toLowerCase();
    const value = Object.prototype.hasOwnProperty.call(context, key)
      ? context[key]
      : Object.prototype.hasOwnProperty.call(context, rawKey)
        ? context[rawKey]
        : match;
    const normalized = String(value ?? "");
    return typeof sanitizer === "function" ? sanitizer(normalized) : normalized;
  });
}

export function resolveRegexTestBenchFindSource(rule, macroContext = {}) {
  const findRegex = String(rule?.findRegex || "");
  switch (Number(rule?.substituteRegex || 0)) {
    case 1:
      return substituteRegexTestBenchMacros(findRegex, macroContext);
    case 2:
      return substituteRegexTestBenchMacros(
        findRegex,
        macroContext,
        sanitizeRegexMacroValue,
      );
    default:
      return findRegex;
  }
}

function parseRegexTestBenchPattern(rule, macroContext = {}) {
  const source = String(
    resolveRegexTestBenchFindSource(rule, macroContext) || "",
  ).trim();
  if (!source) return null;

  const wrapped = source.match(/^\/([\s\S]+)\/([dgimsuvy]*)$/);
  if (wrapped) {
    return new RegExp(wrapped[1], wrapped[2]);
  }

  return new RegExp(source);
}

function filterTrimStrings(value, trimStrings = [], macroContext = {}) {
  let output = String(value ?? "");
  for (const trimString of trimStrings) {
    const needle = substituteRegexTestBenchMacros(
      trimString || "",
      macroContext,
    );
    if (!needle) continue;
    output = output.split(needle).join("");
  }
  return output;
}

export function runRegexTestBenchScript(rule, input, options = {}) {
  const regex = parseRegexTestBenchPattern(rule, options.macroContext);
  if (!regex) {
    return String(input ?? "");
  }

  const macroContext =
    options.macroContext && typeof options.macroContext === "object"
      ? options.macroContext
      : {};
  const content = String(input ?? "");

  return content.replace(regex, (...args) => {
    const replaceString = String(rule?.replaceString || "").replace(
      /\{\{match\}\}/gi,
      "$0",
    );
    const lastArg = args[args.length - 1];
    const groups = lastArg && typeof lastArg === "object" ? lastArg : null;
    const captureEndIndex = groups ? args.length - 3 : args.length - 2;
    const captures = args.slice(0, captureEndIndex);

    const replaceWithGroups = replaceString.replaceAll(
      /\$(\d+)|\$<([^>]+)>|\$0/g,
      (token, num, groupName) => {
        if (token === "$0") {
          return filterTrimStrings(
            captures[0] ?? "",
            rule?.trimStrings,
            macroContext,
          );
        }

        if (num) {
          return filterTrimStrings(
            captures[Number(num)] ?? "",
            rule?.trimStrings,
            macroContext,
          );
        }

        if (groupName) {
          return String(groups?.[groupName] ?? "");
        }

        return "";
      },
    );

    return substituteRegexTestBenchMacros(replaceWithGroups, macroContext);
  });
}

export { sanitizeRegexMacroValue, substituteRegexTestBenchMacros };
