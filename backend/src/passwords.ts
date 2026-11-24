import { randomBytes, scrypt, timingSafeEqual } from "node:crypto";

/**
 * Hash de contraseñas con scrypt (incluido en Node, sin dependencias nativas).
 * Parámetros recomendados por OWASP: N = 2^17, r = 8, p = 1.
 * Los parámetros se guardan junto al hash: si se suben más adelante, las contraseñas viejas
 * se rehashean solas en el próximo login correcto.
 */
export interface ScryptParams {
  N: number;
  r: number;
  p: number;
}

const keyLength = 32;
const saltLength = 16;

function derive(password: string, salt: Buffer, { N, r, p }: ScryptParams): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    scrypt(password.normalize("NFKC"), salt, keyLength, { N, r, p, maxmem: 256 * N * r + 1024 * 1024 }, (error, key) => {
      if (error) {
        reject(error);
      } else {
        resolve(key);
      }
    });
  });
}

export async function hashPassword(password: string, params: ScryptParams): Promise<string> {
  const salt = randomBytes(saltLength);
  const key = await derive(password, salt, params);
  return ["scrypt", params.N, params.r, params.p, salt.toString("base64"), key.toString("base64")].join("$");
}

export async function verifyPassword(
  password: string,
  stored: string,
  current: ScryptParams,
): Promise<{ valid: boolean; needsRehash: boolean }> {
  const [algorithm, N, r, p, saltB64, keyB64] = stored.split("$");
  if (algorithm !== "scrypt" || !N || !r || !p || !saltB64 || !keyB64) {
    return { valid: false, needsRehash: false };
  }

  const params = { N: Number(N), r: Number(r), p: Number(p) };
  const expected = Buffer.from(keyB64, "base64");
  const actual = await derive(password, Buffer.from(saltB64, "base64"), params);
  const valid = actual.length === expected.length && timingSafeEqual(actual, expected);
  const needsRehash = params.N !== current.N || params.r !== current.r || params.p !== current.p;
  return { valid, needsRehash };
}

/**
 * Hash de una contraseña al azar. Cuando el usuario no existe se verifica contra este hash
 * igual, para que la respuesta tarde lo mismo y no revele qué usuarios existen.
 */
let dummyHash: Promise<string> | undefined;
export function getDummyHash(params: ScryptParams): Promise<string> {
  dummyHash ??= hashPassword(randomBytes(24).toString("base64"), params);
  return dummyHash;
}
