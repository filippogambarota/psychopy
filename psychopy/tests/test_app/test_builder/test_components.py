from __future__ import print_function

from pathlib import Path

from past.builtins import unicode

from builtins import object
import os
import io
import pytest
import warnings

from psychopy import constants
from psychopy.experiment import getAllComponents
from psychopy import experiment
from pkg_resources import parse_version

# use "python genComponsTemplate.py --out" to generate a new profile to test against
#   = analogous to a baseline image to compare screenshots
# motivation: catch deviations introduced during refactoring

# what reference to use?
profile = 'componsTemplate.txt'

# always ignore hints, labels, and categories. other options:
# should it be ok or an error if the param[field] order differs from the profile?
ignoreOrder = True

# ignore attributes that are there because inherit from object
ignoreObjectAttribs = True
ignoreList = ['<built-in method __', "<method-wrapper '__", '__slotnames__:']


# profile is not platform specific, which can trigger false positives.
# allowedVals can differ across platforms or with prefs:
ignoreParallelOutAddresses = True

@pytest.mark.components
class TestComponents(object):
    @classmethod
    def setup_class(cls):
        cls.expPy = experiment.Experiment() # create once, not every test
        cls.expJS = experiment.Experiment()
        cls.here = os.path.abspath(os.path.dirname(__file__))
        cls.baselineProfile = os.path.join(cls.here, profile)

        # should not need a wx.App with fetchIcons=False
        try:
            cls.allComp = getAllComponents(fetchIcons=False)
        except Exception:
            import wx
            if parse_version(wx.__version__) < parse_version('2.9'):
                tmpApp = wx.PySimpleApp()
            else:
                tmpApp = wx.App(False)
            try:
                from psychopy.app import localization
            except Exception:
                pass  # not needed if can't import it
            cls.allComp = getAllComponents(fetchIcons=False)

    def setup(self):
        """This setup is done for each test individually
        """
        pass

    def teardown(self):
        pass

    def test_component_attribs(self):
        with io.open(self.baselineProfile, 'r', encoding='utf-8-sig') as f:
            target = f.read()
        targetLines = target.splitlines()
        targetTag = {}
        for line in targetLines:
            try:
                t, val = line.split(':',1)
                targetTag[t] = val
            except ValueError:
                # need more than one value to unpack; this is a weak way to
                # handle multi-line default values, eg TextComponent.text.default
                targetTag[t] += '\n' + line  # previous t value

        param = experiment.Param('', '')  # want its namespace
        ignore = ['__doc__', '__init__', '__module__', '__str__', 'next',
                  '__unicode__', '__native__', '__nonzero__', '__long__']

        # these are for display only (cosmetic) and can end up being localized
        # so typically do not want to check during automated testing, at least
        # not when things are still new-ish and subject to change:
        ignore += ['hint',
                   'label',  # comment-out to compare labels when checking
                   'categ',
                   'next',
                   'dollarSyntax',
                   ]
        for field in dir(param):
            if field.startswith("__"):
                ignore.append(field)
        fields = set(dir(param)).difference(ignore)

        mismatched = []
        for compName in sorted(self.allComp):
            comp = self.allComp[compName](parentName='x', exp=self.expPy)
            order = '%s.order:%s' % (compName, eval("comp.order"))

            if order+'\n' not in target:
                tag = order.split(':',1)[0]
                try:
                    mismatch = order + ' <== ' + targetTag[tag]
                except (IndexError, KeyError): # missing
                    mismatch = order + ' <==> NEW (no matching param in the reference profile)'
                print(mismatch.encode('utf8'))

                if not ignoreOrder:
                    mismatched.append(mismatch)

            for parName in comp.params:
                # default is what you get from param.__str__, which returns its value
                if not constants.PY3:
                    if isinstance(comp.params[parName].val, unicode):
                        comp.params[parName].val = comp.params[parName].val.encode('utf8')
                default = '%s.%s.default:%s' % (compName, parName, comp.params[parName])
                lineFields = []
                for field in fields:
                    if parName == 'name' and field == 'updates':
                        continue
                        # ignore b/c never want to change the name *during a running experiment*
                        # the default name.updates varies across components: need to ignore or standardize
                    f = '%s.%s.%s:%s' % (compName, parName, field, eval("comp.params[parName].%s" % field))
                    lineFields.append(f)

                for line in [default] + lineFields:
                    # some attributes vary by machine so don't check those
                    if line.startswith('ParallelOutComponent.address') and ignoreParallelOutAddresses:
                        continue
                    elif line.startswith('SettingsComponent.OSF Project ID.allowedVals'):
                        continue
                    elif ('SettingsComponent.Use version.allowedVals' in line or
                        'SettingsComponent.Use version.__dict__' in line):
                        # versions available on travis-ci are only local
                        continue
                    origMatch = line+'\n' in target
                    lineAlt = (line.replace(":\'", ":u'")
                                    .replace("\\\\","\\")
                                    .replace("\\'", "'"))
                    # start checking params
                    if not (line+'\n' in target
                            or lineAlt+'\n' in target):
                        # mismatch, so report on the tag from orig file
                        # match checks tag + multi-line, because line is multi-line and target is whole file
                        tag = line.split(':',1)[0]
                        try:
                            mismatch = line + ' <== ' + targetTag[tag]
                        except KeyError: # missing
                            mismatch = line + ' <==> NEW (no matching param in the reference profile)'

                        # ignore attributes that inherit from object:

                        if ignoreObjectAttribs:
                            for item in ignoreList:
                                if item in mismatch:
                                    break
                            else:
                                mismatched.append(mismatch)
                        else:
                            mismatched.append(mismatch)

        for mismatch in mismatched:
            warnings.warn("Non-identical Builder Param: {}".format(mismatch))

    def test_icons(self):
        """Check that all components have icons for each app theme"""
        # Iterate through component classes
        for comp in self.allComp.values():
            # Pathify icon file path
            icon = Path(comp.iconFile)
            # Get paths for each theme
            files = [
                icon.parent / "light" / icon.name,
                icon.parent / "dark" / icon.name,
                icon.parent / "classic" / icon.name,
            ]
            # Check that each path is a file
            for file in files:
                assert file.is_file()

    def test_params_used(self):
        # Add each component only to exp which it is valid for
        rt = self.expPy.addRoutine("onlyRoutine")
        self.expPy.flow.addRoutine(rt, 0)
        rt = self.expJS.addRoutine("onlyRoutine")
        self.expJS.flow.addRoutine(rt, 0)
        for name, component in self.allComp.items():
            if name == "SettingsComponent":
                continue
            if "PsychoPy" in component.targets:
                comp = component(parentName="onlyRoutine", exp=self.expPy)
                self.expPy.routines["onlyRoutine"].append(comp)
            if "PsychoJS" in component.targets:
                comp = component(parentName="onlyRoutine", exp=self.expJS)
                self.expJS.routines["onlyRoutine"].append(comp)
        # Change eyetracking settings
        self.expPy.settings.params['eyetracker'].val = "MouseGaze"
        # Test both python and JS
        for target, exp in {"PsychoPy": self.expPy, "PsychoJS": self.expJS}.items():
            # todo: add JS exceptions
            if target == "PsychoJS":
                continue
            # Compile script
            script = exp.writeScript(target=target)
            # Check that the string value of each param is present in the script
            experiment.utils.scriptTarget = target
            # Iterate through every param
            for routine in exp.flow:
                for comp in routine:
                    for name, param in experiment.getInitVals(comp.params, target).items():
                        # Conditions to skip...
                        if param.val in [
                            "from exp settings",  # units and color space, aliased
                            'first click', 'last click', 'every click',  # PsychoPy.ButtonComponent.save, indirect
                            'last key', 'first key', 'all keys', 'nothing',  # PsychoPy.KeyboardComponent.store, indirect
                            'last button', 'first button', 'all buttons', 'nothing',  # PsychoPy.ioLabsButtonBoxComponent.store, indirect
                            'first look', 'last look', 'every look',  # PsychoPy.RegionOfInterestComponent.save, indirect
                            'default',  # PsychoPy.MicrophoneComponent.device, aliased
                        ]:
                            continue
                        if name in [
                            "startType", "stopType", "durationEstim",  # indirect
                            "timeRelativeTo",  # indirect
                            "Code Type",  # interface-only
                            "refreshDots",  # indirect
                            "interpolate",  # indirect
                            "correctAns",  # conditional
                            "saveJoystickState", "forceEndRoutineOnPress", "saveParamsClickable",  # indirect
                            "sampleRate", "transcribeBackend",  # aliased
                            "saveMouseState",  # indirect
                            "backend",  # aliased
                            "pumpAction",  # indirect
                            "saveFrameValue",  # indirect
                        ]:
                            continue
                        if type(comp).__name__ in ['RatingScaleComponent']:
                            # Deprecated components
                            continue
                        # Check that param is used
                        assert str(param) in script, f"{target}.{type(comp).__name__}.{name}: <psychopy.experiment.params.Param: val={param.val}, valType={param.valType}>"


@pytest.mark.components
def test_flip_before_shutdown_in_settings_component():
    exp = experiment.Experiment()
    script = exp.writeScript()

    assert 'Flip one final time' in script
