# Copyright (C) 2015 Curoverse, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import absolute_import
from __future__ import print_function
import json
import os
import subprocess
import re
import shutil
import urllib
import zipfile

# Python 3 compatibility imports
from six.moves import StringIO
from six import u as unicode

from toil.test import ToilTest, needs_cwl


@needs_cwl
class CWLDirTest(ToilTest):
    """Tests related to the 'Directory' directive"""
    @staticmethod
    def _write_to_json(content, path):
        """Write content to a json file of path"""
        import json
        jobfile_handle = open (path, 'w')
        json.dump(content, jobfile_handle)
        jobfile_handle.close()

    def _create_all_tmpdir(self):
        """create temporary directories and return their paths"""
        tmpdir = self._createTempDir()
        workdir = self._createTempDir()
        outdir = self._createTempDir()
        return (tmpdir, workdir, outdir)

    def test_run_mkdir(self):
        """Test that we can run a cwl step that creates direcotries"""
        self.maxDiff = None
        # create temp dirs
        tmpdir, workdir, outdir = self._create_all_tmpdir()
        # the cwl file with the description of the step
        cwlfile = os.path.join(self._projectRootPath(), 'src/toil/test/cwl/mkdir.cwl')
        input = {'leaf': 'foobaz/bar'}
        jobfile = os.path.join(workdir, 'input.json')
        self._write_to_json(input, jobfile)
        expected = {
            u'dirout': {
                unicode('location'): unicode('file://' + os.path.join(outdir, 'foobaz')),
                unicode('basename'): unicode('foobaz'),
                unicode('class'): unicode('Directory'),
                unicode('nameext'): unicode(""),
                unicode('nameroot'): unicode("foobaz"),
                unicode('listing'): [
                    {
                        unicode('basename'): unicode('bar'),
                        unicode('listing'): [],
                        unicode('class'): unicode('Directory'),
                        unicode('location'): unicode('file://' + os.path.join(outdir, 'foobaz/bar'))
                    }
                ],
            }
        }

        from toil.cwl import cwltoil
        st = StringIO()
        # run the cwl step
        cwltoil.main(['--outdir', outdir, cwlfile, jobfile], stdout=st)
        # get the output
        try:
            out = json.loads(st.getvalue())
        except:
            out = st.getvalue()
        # for future backward compatibility, do not check that expected is exactly the
        # same as observed, but that specific elements match
        for key in ['location', 'basename', 'class', 'nameext', 'nameroot']:
            self.assertEquals(out['dirout'][key], expected['dirout'][key])
        for key in ['basename', 'listing', 'class', 'location']:
            self.assertEquals(out['dirout']['listing'][0][key],
                expected['dirout']['listing'][0][key])
    
    def test_run_ls(self):
        """Test that we can run a cwl step that lists content of a Directory"""
        # some internal functions for readibility
        self.maxDiff = None
        def _populate_input_dir(content, dir):
            """content is a tuple with strings. dir is the path to the
            directory to populate"""
            for f in content:
                fh = open(os.path.join(tmpdir, f), 'w')
                fh.write('%s\n' % f)
                fh.close()
        
        tmpdir, workdir, outdir = self._create_all_tmpdir()
        filenames = ('foo', 'foobar')
        _populate_input_dir(filenames, tmpdir)
        # the cwl file with the description of the step
        cwlfile = os.path.join(self._projectRootPath(), 'src/toil/test/cwl/lsdir.cwl')
        # content of the input file
        input = {'dir': { 'class': 'Directory', 'path': tmpdir }}
        jobfile = os.path.join(workdir, 'jobfile.json')
        self._write_to_json(input, jobfile)

        # set expected output
        expected = {
            unicode('lsout'): {
                unicode('location'): unicode('file://' + os.path.join(outdir, 'output.txt')),
                unicode('basename'): unicode("output.txt"),
                unicode('nameext'): unicode(".txt"),
                unicode('nameroot'): unicode("output"),
                unicode('http://commonwl.org/cwltool#generation'): 0,
                unicode('size'): 11,
                unicode('class'): unicode('File'),
                unicode('checksum'): unicode('sha1$7459c36f90c843dfb3201bfa6299d8921dbbeb08'),
            }
        }

        from toil.cwl import cwltoil
        st = StringIO()
        # run the cwl step
        cwltoil.main(['--outdir', outdir, cwlfile, jobfile], stdout=st)
        # get the output
        try:
            out = json.loads(st.getvalue())
        except:
            out = st.getvalue()
        # # check expected output matches observed
        # self.assertEquals(out, expected)
        # for backward compatibility, do not check that expected is exactly the
        # same as observed, but specific elements match
        for key in ['location', 'basename', 'class', 'nameext', 'nameroot']:
            self.assertEquals(out['lsout'][key], expected['lsout'][key])


@needs_cwl
class CWLTest(ToilTest):

    def _tester(self, cwlfile, jobfile, outDir, expect):
        from toil.cwl import cwltoil
        rootDir = self._projectRootPath()
        st = StringIO()
        cwltoil.main(['--outdir', outDir,
                            os.path.join(rootDir, cwlfile),
                            os.path.join(rootDir, jobfile)],
                     stdout=st)
        out = json.loads(st.getvalue())
        out["output"].pop("http://commonwl.org/cwltool#generation", None)
        out["output"].pop("nameext", None)
        out["output"].pop("nameroot", None)
        self.assertEquals(out, expect)

    def test_run_revsort(self):
        outDir = self._createTempDir()
        self._tester('src/toil/test/cwl/revsort.cwl',
                     'src/toil/test/cwl/revsort-job.json',
                     outDir, {
            # Having unicode string literals isn't necessary for the assertion but makes for a
            # less noisy diff in case the assertion fails.
            u'output': {
                u'location': "file://" + unicode(os.path.join(outDir, 'output.txt')),
                u'basename': unicode("output.txt"),
                u'size': 1111,
                u'class': u'File',
                u'checksum': u'sha1$b9214658cc453331b62c2282b772a5c063dbd284'}})

    def test_restart(self):
        """Enable restarts with CWLtoil -- run failing test, re-run correct test.
        """
        from toil.cwl import cwltoil
        from toil.jobStores.abstractJobStore import NoSuchJobStoreException
        from toil.leader import FailedJobsException
        outDir = self._createTempDir()
        cwlDir = os.path.join(self._projectRootPath(), "src", "toil", "test", "cwl")
        cmd = ['--outdir', outDir, '--jobStore', os.path.join(outDir, 'jobStore'), "--no-container",
               os.path.join(cwlDir, "revsort.cwl"), os.path.join(cwlDir, "revsort-job.json")]
        def path_without_rev():
            return ":".join([d for d in os.environ["PATH"].split(":")
                             if not os.path.exists(os.path.join(d, "rev"))])
        orig_path = os.environ["PATH"]
        # Force a failure and half finished job by removing `rev` from the PATH
        os.environ["PATH"] = path_without_rev()
        try:
            cwltoil.main(cmd)
            self.fail("Expected problem job with incorrect PATH did not fail")
        except FailedJobsException:
            pass
        # Finish the job with a correct PATH
        os.environ["PATH"] = orig_path
        cwltoil.main(["--restart"] + cmd)
        # Should fail because previous job completed successfully
        try:
            cwltoil.main(["--restart"] + cmd)
            self.fail("Restart with missing directory did not fail")
        except NoSuchJobStoreException:
            pass

    def test_run_conformance(self):
        rootDir = self._projectRootPath()
        cwlSpec = os.path.join(rootDir, 'src/toil/test/cwl/spec')
        testhash = "7f510ec768b424601beb8c86700343afe722ac76"
        url = "https://github.com/common-workflow-language/common-workflow-language/archive/%s.zip" % testhash
        if not os.path.exists(cwlSpec):
            urllib.urlretrieve(url, "spec.zip")
            with zipfile.ZipFile('spec.zip', "r") as z:
                z.extractall()
            shutil.move("common-workflow-language-%s" % testhash, cwlSpec)
            os.remove("spec.zip")
        try:
            subprocess.check_output(["bash", "run_test.sh", "RUNNER=toil-cwl-runner", "DRAFT=v1.0"], cwd=cwlSpec,
                                    stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            only_unsupported = False
            # check output -- if we failed but only have unsupported features, we're okay
            p = re.compile(r"(?P<failures>\d+) failures, (?P<unsupported>\d+) unsupported features")
            for line in e.output.split("\n"):
                m = p.search(line)
                if m:
                    if int(m.group("failures")) == 0 and int(m.group("unsupported")) > 0:
                        only_unsupported = True
                        break
            if not only_unsupported:
                raise e
