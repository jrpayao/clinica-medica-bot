import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { AuthAdminService } from '../services/auth-admin.service';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthAdminService);
  const router = inject(Router);

  if (!auth.estaAutenticado()) {
    return router.createUrlTree(['/login']);
  }

  // ADMIN_GLOBAL vai direto para o dashboard — sem forçar seleção de clínica
  return true;
};
