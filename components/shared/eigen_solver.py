"""Sparse generalized eigenanalysis; OpenSees PythonSparse interface, SciPy shift-invert.
Reference: https://opensees.github.io/OpenSeesDocumentation/user/manual/analysis/eigen.html
No mass/stiffness perturbation or dense fallback. Retains massless DOFs.
"""
import time
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import eigsh, splu, LinearOperator

class SparseEigen:
    def solve(self, **kw):
        n, nz, modes = kw['num_eqn'], kw['nnz'], kw['num_modes']
        ptr=np.frombuffer(kw['index_ptr'],dtype=np.int32,count=n+1)
        idx=np.frombuffer(kw['indices'],dtype=np.int32,count=nz)
        K=csr_matrix((np.frombuffer(kw['k_values'],dtype=np.float64,count=nz),idx,ptr),shape=(n,n)).copy()
        M=csr_matrix((np.frombuffer(kw['m_values'],dtype=np.float64,count=nz),idx,ptr),shape=(n,n)).copy()
        K.eliminate_zeros();M.eliminate_zeros()
        if modes >= n: raise ValueError('Sparse eigen mode count must be smaller than active equation count')
        for name,A in [('K',K),('M',M)]:
            error=float(abs(A-A.T).max())/max(float(abs(A).max()),1e-30)
            if error>1e-9: raise RuntimeError(f'{name} is not symmetric: relative asymmetry {error:g}')
        print(f'[EIGEN SPARSE] equations={n} nonzeros={nz} modes={modes}; sparse shift-invert factorization',flush=True)
        started=time.perf_counter()
        import os
        if os.environ.get('OPENSEES_EIGEN_MATRIX_DUMP'):
            from scipy.sparse import save_npz
            from pathlib import Path
            out=Path(os.environ['OPENSEES_EIGEN_MATRIX_DUMP']);out.mkdir(parents=True,exist_ok=True)
            save_npz(out/'K.npz',K);save_npz(out/'M.npz',M)
        from threadpoolctl import threadpool_limits
        with threadpool_limits(limits=1):
            factor=splu(K.tocsc())
            print(f'[EIGEN FACTORIZED] elapsed={time.perf_counter()-started:.3f}s; solving {modes} modes',flush=True)
            inverse=LinearOperator(K.shape,matvec=factor.solve,dtype=np.float64)
            vals,vecs=eigsh(K,k=modes,M=M,OPinv=inverse,sigma=0.0,which='LM',tol=1e-8,maxiter=3000,ncv=min(n,max(2*modes+1,40)),v0=np.random.default_rng(160).normal(size=n))
        order=np.argsort(vals);vals=vals[order];vecs=vecs[:,order]
        residuals=[]
        for i,v in enumerate(vals):
            x=vecs[:,i];kx=K@x;mx=M@x
            residuals.append(float(np.linalg.norm(kx-v*mx)/max(np.linalg.norm(kx)+abs(v)*np.linalg.norm(mx),1e-30)))
        if max(residuals)>1e-5:raise RuntimeError(f'Eigen residual verification failed: {max(residuals):g}')
        if not np.all(np.isfinite(vals)) or np.any(vals<=0):raise RuntimeError('Nonpositive eigenvalues: inspect model stability')
        np.frombuffer(kw['eigenvalues'],dtype=np.float64,count=modes)[:]=vals
        np.frombuffer(kw['eigenvectors'],dtype=np.float64,count=n*modes)[:]=vecs.T.ravel()
        print(f'[EIGEN COMPLETE] sparse solve={time.perf_counter()-started:.3f}s max relative residual={max(residuals):.3g}',flush=True)

def solve_eigen(ops, modes, solver='PythonSparse'):
    modes=int(modes)
    started=time.perf_counter()
    print(f'[EIGEN START] solver={solver} modes={modes} nodes={len(ops.getNodeTags())} elements={len(ops.getEleTags())}',flush=True)
    if solver=='PythonSparse':
        values=ops.eigen('PythonSparse',modes,{'solver':SparseEigen(),'scheme':'CSR'})
    else:
        reason=None
        if solver=='-fullGenLapack' and len(ops.getNodeTags())>500:
            reason=f'Dense fullGenLapack is disabled above 500 nodes (model has {len(ops.getNodeTags())}); avoiding an unsafe dense allocation'
        else:
            try:
                values=list(ops.eigen(str(solver),modes))
                if len(values)!=modes:
                    reason=f'{solver} returned {len(values)} of {modes} requested modes'
                elif any(not np.isfinite(float(value)) or float(value)<=0 for value in values):
                    reason=f'{solver} returned a non-finite or non-positive eigenvalue'
            except Exception as exc:
                reason=f'{solver} failed: {type(exc).__name__}: {exc}'
        if reason:
            print(f'[EIGEN FALLBACK] requested={solver}; using PythonSparse; reason={reason}',flush=True)
            try:
                values=ops.eigen('PythonSparse',modes,{'solver':SparseEigen(),'scheme':'CSR'})
            except Exception as exc:
                raise RuntimeError(
                    f'{solver} could not provide {modes} modes ({reason}); '
                    f'PythonSparse fallback also failed: {type(exc).__name__}: {exc}'
                ) from exc
    print(f'[EIGEN RETURN] elapsed={time.perf_counter()-started:.3f}s modes={len(values)}',flush=True)
    return values
