import { inject } from '@angular/core';
import { CanActivateChildFn, Router } from '@angular/router';
import { AuthAdminService } from '../services/auth-admin.service';
import { rotaInicial, rotaPermitida } from '../services/perfil';

/** Impede que um perfil operacional abra, pela URL, uma tela fora do seu menu. */
export const perfilGuard: CanActivateChildFn = (_rota, estado) => {
  const role = inject(AuthAdminService).usuario()?.role;
  if (rotaPermitida(role, estado.url)) return true;
  return inject(Router).createUrlTree([rotaInicial(role)]);
};
