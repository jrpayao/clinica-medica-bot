import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthAdminService } from './auth-admin.service';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthAdminService);
  const token = auth.getToken();

  if (token) {
    return next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }));
  }
  return next(req);
};
