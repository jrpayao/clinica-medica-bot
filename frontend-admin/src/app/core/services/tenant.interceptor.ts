import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AuthAdminService } from './auth-admin.service';

/**
 * Interceptor de tenant: adiciona o header X-Estabelecimento-ID em todas as
 * requests quando ADMIN_GLOBAL está em modo global (JWT sem est_id) e tem um
 * estabelecimento selecionado no filtro global do toolbar.
 *
 * O backend (get_estabelecimento_id) lê este header para resolver o tenant
 * em todos os endpoints que usam require_estabelecimento.
 */
export const tenantInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthAdminService);
  const usuario = auth.usuario();

  // Apenas ADMIN_GLOBAL em modo global (JWT sem est_id) com filtro ativo
  if (
    usuario?.role === 'ADMIN_GLOBAL' &&
    !usuario?.estabelecimentoId &&
    auth.estabelecimentoAtivoId() !== null
  ) {
    return next(
      req.clone({
        setHeaders: { 'X-Estabelecimento-ID': String(auth.estabelecimentoAtivoId()) },
      }),
    );
  }

  return next(req);
};
