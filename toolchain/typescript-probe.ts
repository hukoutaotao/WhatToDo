// Bounded native TypeScript/JavaScript runtime comparison, not a second app.
// Node strips these types; this run does not claim a tsc type-check/build.
const before: string = "2026-01-01T00:00:00.000000Z";
const after: string = "2026-01-01T00:00:00.000001Z";
console.log(JSON.stringify({
  node: process.version,
  beijing: new Intl.DateTimeFormat("en-GB", {
    timeZone: "Asia/Shanghai", year: "numeric", month: "2-digit",
    day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
  }).format(new Date("2026-01-01T16:00:00Z")),
  nativeDateMicrosecondDeltaMs: Date.parse(after) - Date.parse(before),
  numberLargeIntegerEquality: Number(9007199254740992n) === Number(9007199254740993n),
  bigintLargeIntegerEquality: 9007199254740992n === 9007199254740993n,
}));
