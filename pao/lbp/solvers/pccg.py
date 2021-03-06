#
# A solver for linear bilevel programs using
# using projected column constraint generation
# "A projection-based reformulation and decomposition algorithm for global optimization 
#  of a class of mixed integer bilevel linear programs" by Dajun Yue, Jiyao Gao, Bo Zeng, Fengqi You
#
# Adapted from an implementation by She'ifa Punla-Green at Sandia National Labs
#
#This algorithm seeks to solve the following bilevel MILP:
#    min cR*xu + cZ*yu + dR*xl0 + dZ*yl0 
#    s.t. AR*xu + AZ*yu + BR*xl0 + BZ* yl0 <= r
#     (xl0,yl0) in argmax {wR*xl+wZ*yl: PR*xl+PZ*yl<=s-QR*xu-QZ*yu}
#
import time
import numpy as np
import pyutilib
import pyomo.environ as pe
import pyomo.opt
from pyomo.mpec import ComplementarityList, complements
from ..solver import SolverFactory, LinearBilevelSolverBase, LinearBilevelResults
from ..repn import LinearBilevelProblem
from ..convert_repn import convert_LinearBilevelProblem_to_standard_form, convert_sense, convert_binaries_to_integers
from .. import pyomo_util
from .pccg_solver import execute_PCCG_solver


@SolverFactory.register(
        name='pao.lbp.PCCG',
        doc='A solver for linear bilevel programs using using projected column constraint generation')
class LinearBilevelSolver_PCCG(LinearBilevelSolverBase):

    def __init__(self, **kwds):
        super().__init__(name='pao.lbp.PCCG')
        self.config.epsilon = 1e-4      #For use in disjunction approximation
        self.config.xi = 0              #tolerance for UB-LB to claim convergence
        self.config.maxit = None        #Maximum number of iterations
        self.config.bigm = 1e6          # upper bound on variables
        self.config.solver = 'gurobi'
        self.config.quiet = True


    def check_model(self, lbp):
        #
        # Confirm that the LinearBilevelProblem is well-formed
        #
        assert (type(lbp) is LinearBilevelProblem), "Solver '%s' can only solve a LinearBilevelProblem" % self.name
        lbp.check()
        #
        assert (len(lbp.U.LL) == 1), "Can only solve linear bilevel problems with one lower-level"
        #
        assert (len(lbp.U.LL.LL) == 0), "Can only solve bilevel problems"

    def solve(self, lbp, options=None, **config_options):
        #
        # Error checks
        #
        self.check_model(lbp)
        #
        # Process keyword options
        #
        self._update_config(config_options)
        #
        # Start clock
        #
        start_time = time.time()

        # PCCG requires a standard form with inequalities and 
        # a maximization lower-level
        self.standard_form, soln_manager = convert_LinearBilevelProblem_to_standard_form(lbp, inequalities=True)
        convert_sense(self.standard_form.U.LL, minimize=False)
        
        results = LinearBilevelResults(solution_manager=soln_manager)

        UxR, UxZ, LxR, LxZ = execute_PCCG_solver(self.standard_form, self.config, results)
        xR = {lbp.U.id:UxR, lbp.U.LL[0].id:LxR}
        xZ = {lbp.U.id:UxZ, lbp.U.LL[0].id:LxZ}
        results.copy_from_to(LxR=xR, LxZ=xZ, lbp=lbp)

        results.solver.wallclock_time = time.time() - start_time
        return results
