// Express Request augmentation — adds userId set by the auth middleware.
import "express";

declare global {
  namespace Express {
    interface Request {
      userId?: string;
    }
  }
}

export {};
