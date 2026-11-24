/** Error esperado de negocio: se devuelve al cliente con su código HTTP y un código legible. */
export class AppError extends Error {
  constructor(
    readonly statusCode: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}

export const notFound = (what: string) => new AppError(404, "not_found", `${what} no existe.`);
