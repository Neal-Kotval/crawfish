/**
 * Tiny ULID generator (Crockford base32, 26 chars).
 *   - 10 chars timestamp (ms since epoch)
 *   - 16 chars randomness
 * Lowercase to match the org_id convention in spec §1.
 */
import { randomBytes } from "node:crypto";
const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"; // Crockford
const TIME_LEN = 10;
const RAND_LEN = 16;
function encodeTime(now, len) {
    let s = "";
    for (let i = len - 1; i >= 0; i--) {
        const mod = now % 32;
        s = ALPHABET[mod] + s;
        now = Math.floor(now / 32);
    }
    return s;
}
function encodeRandom(len) {
    const bytes = randomBytes(len);
    let s = "";
    for (let i = 0; i < len; i++) {
        s += ALPHABET[bytes[i] % 32];
    }
    return s;
}
export function ulid() {
    return (encodeTime(Date.now(), TIME_LEN) + encodeRandom(RAND_LEN)).toLowerCase();
}
