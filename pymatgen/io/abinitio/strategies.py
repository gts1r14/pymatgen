"""
Strategy objects used to create Abinit input files for particular types of calculations.
"""
from __future__ import division, print_function

import abc
import collections
import numpy as np

from pprint import pprint, pformat

from pymatgen.util.string_utils import str_aligned, str_delimited
from .abiobjects import SpinMode, Smearing, Electrons
from .pseudos import PseudoTable
#from .input import SystemCard, ElectronsCard, ControlCard, KpointsCard, Input, select_pseudos
from .input import select_pseudos

__author__ = "Matteo Giantomassi"
__copyright__ = "Copyright 2013, The Materials Project"
__version__ = "0.1"
__maintainer__ = "Matteo Giantomassi"
__email__ = "gmatteo at gmail.com"
__status__ = "Development"
__date__ = "$Feb 21, 2013M$"

##########################################################################################

# TODO
#class ScfStrategyFactory(object):
#    """
#    Abstract factory for strategies. Returns a concrete factory
#
#    Example: abstract_factory = ScfStrategyFactory()
#        factory = abstract_factory()
#        scf_strategy = factory.make_strategy()
#    """
#    __metaclass__ = abc.ABCMeta
#        
#    #def __init__(self, mode, accuracy):
#        # Dict with Ground-State strategy subclasses
#        gs_subclasses = {}
#        for klass in Scftrategy.__subclasses__():
#            gs_subclasses[klass.__name__] = klass

##########################################################################################

class Strategy(object):
    """
    A Strategy object generates the abinit input file used for a particular type of calculation
    e.g. ground-state runs, structural relaxations, self-energy calculations ...

    A Strategy can absorb data (e.g. data produced in the previous steps of a workflow) and 
    can use this piece of information to generate/optimize the input variables.
    Strategy objects must provide the method make_input that builds and returns the abinit input file.

    Attributes:
        accuracy:
            Accuracy of the calculation used to define basic parameters of the run.
            such as tolerances, basis set truncation ... 
        pseudos:
    """
    __metaclass__ = abc.ABCMeta

    # Mapping runlevel --> optdriver variable
    _runl2optdriver = {
        "scf"      : 0 , 
        "nscf"     : 0 ,
        "relax"    : 0 ,
        "dfpt"     : 1 ,
        "screening": 3 ,
        "sigma"    : 4 ,
        "bse"      : 99,
    }

    # Name of the (default) tolerance used by the runlevels.
    _runl2tolname = {
        "scf"      : 'tolvrs', 
        "nscf"     : 'tolwfr', 
        "dfpt"     : 'toldfe',   # ?
        "screening": 'toldfe',   # dummy
        "sigma"    : 'toldfe',   # dummy
        "bse"      : 'toldfe',   # ?
    }

    # Tolerances for the different levels of accuracy.
    T = collections.namedtuple('Tolerance', "low normal high")
    _tolerances = {
        "toldfe": T(1.e-9,  1.e-10, 1.e-11), 
        "tolvrs": T(1.e-7,  1.e-8,  1.e-9),
        "tolwfr": T(1.e-15, 1.e-17, 1.e-19),
        "tolrdf": T(0.04,   0.02,   0.01),
        }
    del T

    def __str__(self):
        return "<%s at %s, accuracy = %s>" % (self.__class__.__name__, id(self), self.accuracy)

    @abc.abstractproperty
    def runlevel(self):
        "String defining the Runlevel. See _runl2optdriver"
                                                            
    @property
    def optdriver(self):
        "The optdriver associated to the calculation"
        return self._runl2optdriver[self.runlevel]

    def learn(self, **data):
        "Update the data stored in self"
        if not hasattr(self, "_data"):
            self._data = dict(data)
        else:
            if [k in self._data for k in data].count(True) != 0:
                raise ValueError("Keys %s are already present in data" % str([k for k in data]))
            self._data.update(data)

    @property
    def accuracy(self):
        "Accuracy used by the strategy"
        try:
            return self._accuracy
        except AttributeError:
            self.set_accuracy("normal")
            return self._accuracy

    def set_accuracy(self, accuracy):
        "Accuracy setter"
        if hasattr(self, "_accuracy"):
            raise RuntimeError("object already has accuracy %s " % self._accuracy)

        assert accuracy in ["low", "normal", "high",]
        self._accuracy = accuracy

    @property
    def data(self):
        try:
            return self. _data
        except AttributeError:
            return {}

    @property
    def isnc(self):
        "True if norm-conserving calculation"
        return self.pseudos.allnc
                                              
    @property
    def ispaw(self):
        "True if PAW calculation"
        return self.pseudos.allpaw

    @property
    def ecut(self):
        try:
            return self.extra_abivars["ecut"] # User option.
        except KeyError:
            # Compute ecut from the Pseudo Hints.
            hints = [p.hint_for_accuracy(self.accuracy) for p in self.pseudos]
            return max(hint.ecut for hint in hints)

    @property
    def pawecutdg(self):
        if not self.ispaw:
            return None
        try:
            return self.extra_abivars["pawecutdg"] # User option.
        except KeyError:
            raise NotImplementedError("")
            #ratio = max(p.suggested_augratio(accuracy) for p in self.pseudos])
            #ratio = augration_high if high else augratio_norm 
            #pawecutdg = ecut * ratio

    @property
    def tolerance(self):
        "Return a dict {varname: varvalue} with the tolerance to be used for the run"
        # Check user options first.
        for tolname in self._tolerances:
            try:
                return {name: self.extra_abivars[tolname]}
            except KeyError:
                pass

        # Use default values depending on the runlevel and the accuracy.
        tolname = self._runl2tolname[self.runlevel]
        return {tolname: getattr(self._tolerances[tolname], self.accuracy)}

    #@property 
    #def nsppol(self): 
    #    return self.electrons.spin_mode.nsppol
    #                                   
    #@property 
    #def nspinor(self): 
    #    return self.electrons.spin_mode.nspinor
    #                                   
    #@property 
    #def nspden(self): 
    #    return self.electrons.spin_mode.nspden

    @property
    def need_forces(self):
        "True if forces are required at each SCF step (like the stresses)."
        return self.runlevel in ["relax",]
                                                                            
    @property
    def need_stress(self):
        "True if the computation of the stress is required"
        # TODO: here it's easier to check if optcell != 0
        return self.runlevel in ["relax",]

    def add_extra_abivars(self, abivars):
        "Add variables (dict) to extra_abivars"
        self.extra_abivars.update(abivars)

    #def iocontrol(self):
    #    "Dictionary with variables controlling the IO"
    #    ptrwf = self.extra_abivars.get("prtwf")
    #    
    #    d = {"prtwf" : prtwf if prtwf is not None else 0
    #         "prtden": 1,
    #         "prtgkk": 1 if self.runlevel == "dfpt" else None
    #        }
    #    return d

    #def speedup(self):
    #    "Dictionary with the variables that have a significant impact on the WallTime."
    #     boxcutmin = self.extra_abivars.get("boxcutmin")
    #     if boxcutmin is None and self.accuracy == "low": boxcutime = 0.75

    #    "optforces": None if (self.need_forces or want_forces) else 2,
    #    "optstress": None if (self.need_stress or want_stress) else 0,

    #    d = {"boxcutmin": boxcutmin,
    #         "optforces": optforces, 
    #         "optstress": optstress, 
    #        }
    #    return d

    @abc.abstractmethod
    def make_input(self, *args, **kwargs):
        "Returns an Input instance"

##########################################################################################

class ScfStrategy(Strategy):
    """
    Strategy for ground-state SCF calculations.
    """
    def __init__(self, structure, pseudos, ksampling, accuracy="normal", spin_mode="polarized", 
                 smearing="fermi_dirac:0.1 eV", charge=0.0, scf_algorithm=None, use_symmetries=True, **extra_abivars):
        """
        Args:
            structure:
                pymatgen structure
            pseudos:
                List of pseudopotentials.
            ksampling:
                Ksampling object defining the sampling of the BZ.
            accuracy:
                Accuracy of the calculation.
            spin_mode: 
                Spin polarization mode.
            smearing: 
                string or Smearing instance. 
            charge:
                Total charge of the system. Default is 0.
            scf_algorithm:
                ElectronsAlgorithm instance.
            use_symmetries:
                False if point group symmetries should not be used.
            extra_abivars:
                Extra variables that will be directly added to the input file.
        """
        super(ScfStrategy, self).__init__()

        self.set_accuracy(accuracy)

        self.structure  = structure
        self.pseudos    = select_pseudos(pseudos, structure)
        self.ksampling  = ksampling
        self.use_symmetries = use_symmetries

        self.electrons  = Electrons(spin_mode = spin_mode,
                                    smearing  = smearing,
                                    algorithm = scf_algorithm,
                                    nband     = None,
                                    fband     = None,
                                    charge    = charge,
                                   )

        self.extra_abivars = extra_abivars

        #abivars.update({"nsym": 1 if not self.use_symmetries else None})

    @property
    def runlevel(self):
        return "scf"

    def make_input(self):
        extra = {"optdriver": self.optdriver,
                 "ecut"     : self.ecut,
                 "pawecutdg": self.pawecutdg,
                }
        extra.update(self.tolerance)

        input = InputWriter(self.structure, self.electrons, self.ksampling, **extra)
        print(input.get_string())

        return input.get_string()

##########################################################################################

class NscfStrategy(Strategy):
    """
    Strategy for non-self-consiste calculations.
    """
    def __init__(self, scf_strategy, ksampling, nscf_nband, nscf_algorithm=None, **extra_abivars):
        """
        Args:
            scf_strategy:
                ScfStrategy used for the GS run.
            ksampling:
                Ksampling object defining the sampling of the BZ.
            nscf_nband:
                Number of bands to compute.
            nscf_algorithm
                ElectronsAlgorithm instance.
            extra_abivars:
                Extra ABINIT variables that will be directly added to the input file
        """
        super(NscfStrategy, self).__init__()

        self.set_accuracy(scf_strategy.accuracy)

        self.scf_strategy = scf_strategy

        self.nscf_nband = nscf_nband
        self.pseudos    = scf_strategy.pseudos
        self.ksampling  = ksampling

        if nscf_algorithm:
            self.nscf_algorithm = nscf_algorithm
        else:
            self.nscf_algorithm = {"iscf": -3}

        # Electrons used in the GS run.
        scf_electrons = scf_strategy.electrons

        self.electrons  = Electrons(spin_mode = scf_electrons.spin_mode,
                                    smearing  = scf_electrons.smearing,
                                    algorithm = nscf_algorithm,
                                    nband     = nscf_nband,
                                    fband     = None,
                                    charge    = scf_electrons.charge,
                                    comment   = None,
                                    #occupancies = None,
                                   )

        self.extra_abivars = extra_abivars

    @property
    def runlevel(self):
        return "nscf"

    def make_input(self):
        # Initialize the system section from structure.
        scf_strategy = self.scf_strategy

        extra = {"optdriver": self.optdriver,
                 "ecut"     : self.ecut,
                 "pawecutdg": self.pawecutdg,
                }
        extra.update(self.tolerance)
                                                                                     
        input = InputWriter(scf_strategy.structure, self.electrons, self.ksampling, **extra)
        print(input.get_string())

        return input.get_string()

##########################################################################################

class RelaxStrategy(ScfStrategy):

    def __init__(structure, pseudos, ksampling, relax_algo, accuracy="normal", spin_mode="polarized", 
                 smearing="fermi_dirac:0.1 eV", charge=0, scf_algorithm=None, **extra_abivars):
        """
        Args:
            structure:
                pymatgen structure
            pseudos:
                List of pseudopotentials.
            ksampling:
                Ksampling object defining the sampling of the BZ.
            accuracy:
                Accuracy of the calculation.
            spin_mode: 
                Flag defining the spin polarization (nsppol, nspden, nspinor). Defaults to "polarized"
            smearing: 
                String or Smearing instance. 
            charge:
                Total charge of the system. Default is 0.
            scf_algorithm:
                ElectronsAlgorithm instance.
            extra_abivars:
                Extra ABINIT variables that will be directly added to the input file
        """
        super(RelaxStrategy, self).__init__(structure, pseudos, ksampling, 
                 accuracy=accuracy, spin_mode=spin_mode, smearing=smearing, 
                 charge=charge, scf_algorithm=scf_algorithm, **extra_abivars)

        self.relax_algo = relax_algo

    @property
    def runlevel(self):
        return "scf"

    def make_input(self):
        # Initialize the system section from structure.
        raise NotImplementedError("")
        #system = self._make_systemcard()
        ## Variables for electrons.
        #electrons = self._make_electronscard()
        #kpoints = self._make_kpointscard()
        #relax = self._make_relaxcard()
        #control = ControlCard(system, electrons, kmesh, relax, **self.extra_abivars)
        #return Input(system, electrons, kpoints, relax, control)

##########################################################################################

class ScreeningStrategy(Strategy):

    def __init__(self, scf_strategy, nscf_strategy, screening, **extra_abivars):
        """
        Constructor for screening calculations.
                                                                                                       
        Args:
            scf_strategy:
                Strategy used for the ground-state calculation
            nscf_strategy:
                Strategy used for the non-self consistent calculation
            screening:
                Screening instance
            extra_abivars:
                Extra ABINIT variables added directly to the input file
        """
        super(ScreeningStrategy, self).__init__()

        self.scf_strategy = scf_strategy
        self.nscf_strategy = nscf_strategy
        self.screening = screening

        self.extra_abivars = extra_abivars

        nscf_electrons = nscf_strategy.electrons
        nscf_nband = nscf_electrons.nband
        scr_nband  = nscf_nband 

        self.ksampling  = nscf_strategy.ksampling

        self.electrons  = Electrons(spin_mode = nscf_electrons.spin_mode,
                                    smearing  = nscf_electrons.smearing,
                                    algorithm = nscf_algorithm,
                                    nband     = scr_nband,
                                    charge    = nscf_electrons.charge,
                                    comment   = None,
                                   )
    @property
    def runlevel(self):
        return "screening"

    def make_input(self):
        raise NotImplementedError("")
        #scr_cards = nscf_input.copy_cards(exclude=["ElectronsCard",])
        #nscf_electrons = self.nscf_strategy.electrons
        #nscf_nband = nscf_electrons.nband
        #nband_screening = nscf_nband 
        #scr_cards.append(ElectronsCard(spin_mode=nscf_input.spin_mode, nband=nband_screening, smearing=smearing))
        #raise NotImplementedError("")
        #scr_cards.append(ScreeningCard(scr_strategy, comment="Generated from NSCF input"))
        #scr_cards.append(ControlCard(*scr_cards, **kwargs))
        #return Input(*scr_cards)

##########################################################################################

class SelfEnergyStrategy(Strategy):

    def __init__(self, scf_strategy, nscf_strategy, scr_strategy, **extra_abivars):
        """
        Constructor for screening calculations.
                                                                                                       
        Args:
            scf_strategy:
                Strategy used for the ground-state calculation
            nscf_strategy:
                Strategy used for the non-self consistent calculation
            scr_strategy
                Strategy used for the screening calculation
            extra_abivars:
                Extra ABINIT variables added directly to the input file
        """
        # TODO Add consistency check between SCR and SIGMA strategies

        super(ScreeningStrategy, self).__init__()

        self.scf_strategy = scf_strategy
        self.nscf_strategy = nscf_strategy
        self.scr_strategy = scr_strategy

        self.extra_abivars = extra_abivars

    @property
    def runlevel(self):
        return "sigma"

    def make_input(self):
        raise NotImplementedError("")
        #smearing = Smearing.assmearing(smearing)
        #if (smearing != scr_input.smearing):
        #    raise ValueError("Input smearing differs from the one used in the SCR run")
        #sigma_nband = sigma_strategy.get_varvalue("nband")
        #raise NotImplementedError("")
        #se_card = SelfEnergyCard(sigma_strategy, comment="Generated from SCR input")
        #se_card = SelfEnergyCard(sigma_strategy, comment="Generated from SCR input")
        #sigma_cards = scr_input.copy_cards(exclude=["ScreeningCard", "ElectronsCard",])
        #sigma_cards.append(ElectronsCard(spin_mode=scr_input.spin_mode, nband=sigma_nband, smearing=smearing))
        #sigma_cards.append(se_card)
        #sigma_cards.append(ControlCard(*sigma_cards, **extra_abivars))
        #return Input(*sigma_cards)

##########################################################################################

class InputWriter(object): 
    """
    Base class representing a set of Abinit input parameters associated to a particular topic. 
    Essentially consists of a dictionary with some helper functions.

    The objects are stored in the dictionary as {obj.__class__.__name__: obj}

    str(self) returns a string with the corresponding section of the abinit input file.
    """
    def __init__(self, *args, **kwargs):
        self.abiobj_dict = collections.OrderedDict()
        self.extra_abivars = collections.OrderedDict()

        for arg in args:
            if hasattr(arg, "to_abivars"):
                self.add_abiobj(arg)
            else:
                self.add_extra_abivars(arg)

        for (k,v) in kwargs.items():
            self.add_extra_abivars({k:v})

    def __str__(self):
        "String representation (the section of the abinit input file)"
        return self.get_string()

    @property
    def abiobjects(self):
        "List of objects stored in self"
        return self.abiobj_dict.values()

    def add_abiobj(self, obj):
        "Add the object to the card"
        if not hasattr(obj, "to_abivars"):
            raise ValueError("%s does not define the method to_abivars" % str(obj))

        cname = obj.__class__.__name__
        if cname in self.abiobj_dict:
            raise ValueError("%s is already in the Card" % cname)
        self.abiobj_dict[cname] = obj

    def add_extra_abivars(self, abivars):
        "Add variables (dict) to extra_abivars"
        self.extra_abivars.update(abivars)

    def to_abivars(self):
        "Returns a dictionary with the abinit variables defined by the Card"
        abivars = {}
        for obj in self.abiobjects:
            abivars.update(obj.to_abivars())

        abivars.update(self.extra_abivars)
        return abivars

    #def list_objects(self):
    #    "String comment (comment of self + comments of the objects, if any)"
    #    for obj in self.abiobjects:
    #        if hasattr(obj, "comment"):
    #            lines.append("%s: %s" % (obj.__class__.__name__, obj.comment))
    #    return "\n".join(lines)

    @staticmethod
    def _format_kv(key, value):
        # Use default values if value is None.
        if value is None: 
            return []
                                                                                   
        if isinstance(value, collections.Iterable) and not isinstance(value, str):
            arr = np.array(value)
                                                                                   
            if len(arr.shape) in [0,1]: # scalar or vector.
                token = [key, " ".join([str(i) for i in arr])]
                                                                                   
            else: 
                # array --> matrix 
                matrix = np.reshape(arr, (-1, arr.shape[-1])) 
                for (idx, row) in enumerate(matrix):
                    kname = key +"\n" if idx == 0 else ""
                    token = [kname, " ".join([str(i) for i in row])]
                                                                                   
        else:
            token = [key, value]

        return token

    def get_string(self, pretty=False):
        """
        Returns a string representation of self. The reason why this
        method is different from the __str__ method is to provide options for pretty printing.

        Args:
            pretty:
                Set to True for pretty aligned output. Defaults to False.
        """
        lines = []

        # Write the Abinit objects.
        for obj in self.abiobjects:
            lines.append([80*"#", ""])
            lines.append(["#", "%s" % obj.__class__.__name__])
            lines.append([80*"#", ""])
            for (k, v) in obj.to_abivars().items():
                lines.append(self._format_kv(k, v))

        if self.extra_abivars:
            lines.append([80*"#", ""])
            lines.append(["#", "Extra_Abivars"])
            lines.append([80*"#", ""])
            for (k, v) in self.extra_abivars.items():
                lines.append(self._format_kv(k, v))

        if pretty:
            return str_aligned(lines, header=None)
        else:
            return str_delimited(lines, header=None, delimiter=5*" ")

    #def diff(self, other):
    #    """
    #    Diff function for Card.  Compares two objects and indicates which
    #    parameters are the same and which are not. Useful for checking whether
    #    two runs were done using the same parameters.
                                                                                    
    #    Args:
    #        other:
    #            The other Card object to compare to.
                                                                                    
    #    Returns:
    #        Dict of the following format:
    #        {"Same" : parameters_that_are_the_same,
    #        "Different": parameters_that_are_different}
    #        Note that the parameters are return as full dictionaries of values.
    #        E.g. {"natom":3}
    #    """
    #    similar_param, different_param = {}, {}
    #    for (k1, v1) in self.items():
    #        if k1 not in other:
    #            different_param[k1] = {self.name : v1, other.name : "Default"}
    #        elif v1 != other[k1]:
    #            different_param[k1] = {self.name : v1, other.name : other[k1]}
    #        else:
    #            similar_param[k1] = v1
                                                                                    
    #    for (k2, v2) in other.items():
    #        if k2 not in similar_param and k2 not in different_param:
    #            if k2 not in self:
    #                different_param[k2] = {self.name : "Default", other.name : v2}
                                                                                    
    #    return {"Same": similar_param, "Different": different_param}

