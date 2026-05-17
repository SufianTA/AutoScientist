const SECRET_PATTERNS = [
  new RegExp(`sk-${"ant"}-`, "i"),
  new RegExp(`sk-${"proj"}-`, "i"),
  /sk-[A-Za-z0-9_-]{20,}/i,
  new RegExp(`${"AI"}za[0-9A-Za-z_-]{20,}`),
  /xox[baprs]-/i,
  new RegExp(`BEGIN ${"PRIVATE"} KEY`, "i")
];

const ENV_VAR_PATTERN = /^[A-Za-z_][A-Za-z0-9_]{0,127}$/;

export function looksLikeSecret(value: string) {
  const text = value.trim();
  return text.length > 128 || SECRET_PATTERNS.some((pattern) => pattern.test(text));
}

export function validateEnvVarName(value: string) {
  const text = value.trim();
  if (!text) return null;
  if (looksLikeSecret(text)) {
    return "Paste only an environment variable name here, for example ANTHROPIC_API_KEY. Put the raw key in .env.";
  }
  if (!ENV_VAR_PATTERN.test(text)) {
    return "Environment variable names can contain only letters, numbers, and underscores.";
  }
  return null;
}
