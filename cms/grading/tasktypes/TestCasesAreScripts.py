#!/usr/bin/env python3

import logging
import os

from cms.db import Executable
from cms.grading.ParameterTypes import ParameterTypeCollection, \
    ParameterTypeChoice, ParameterTypeString
from cms.grading.languagemanager import LANGUAGES, get_language
from cms.grading.steps import compilation_step, evaluation_step, \
    human_evaluation_message
from . import TaskType, \
    check_executables_number, check_files_number, check_manager_present, \
    create_sandbox, delete_sandbox, eval_output, is_manager_for_compilation


logger = logging.getLogger(__name__)


# Dummy function to mark translatable string.
def N_(message):
    return message


class TestCasesAreScripts(TaskType):
    # Codename of the checker, if it is used.
    CHECKER_CODENAME = "checker"
    # Basename of the grader, used in the manager filename and as the main
    # class in languages that require us to specify it.
    GRADER_BASENAME = "grader"
    # Default input and output filenames when not provided as parameters.
    DEFAULT_INPUT_FILENAME = "input.txt"
    DEFAULT_OUTPUT_FILENAME = "output.txt"

    # Constants used in the parameter definition.
    OUTPUT_EVAL_DIFF = "diff"
    OUTPUT_EVAL_CHECKER = "comparator"
    COMPILATION_ALONE = "alone"
    COMPILATION_GRADER = "grader"

    # Other constants to specify the task type behaviour and parameters.
    ALLOW_PARTIAL_SUBMISSION = False

    _EVALUATION = ParameterTypeChoice(
        "Output evaluation",
        "output_eval",
        "",
        {OUTPUT_EVAL_DIFF: "Outputs compared with white diff",
         OUTPUT_EVAL_CHECKER: "Outputs are compared by a comparator"})

    ACCEPTED_PARAMETERS = [_EVALUATION]

    @property
    def name(self):
        """See TaskType.name."""
        # TODO add some details if a grader/comparator is used, etc...
        return "TestCasesAreScripts"
    
    testable = False

    def __init__(self, parameters):
        super().__init__(parameters)

        self.output_filename = ""
        self.output_eval = self.parameters[0]
        self._actual_input = self.DEFAULT_INPUT_FILENAME
        self._actual_output = self.DEFAULT_OUTPUT_FILENAME
    
    def get_compilation_commands(self, unused_submission_format):
        """See TaskType.get_compilation_commands."""
        return None

    def get_user_managers(self):
        """See TaskType.get_user_managers."""
        return []

    def get_auto_managers(self):
        """See TaskType.get_auto_managers."""
        return []

    def _uses_checker(self):
        return self.output_eval == self.OUTPUT_EVAL_CHECKER

    def _uses_grader(self):
        return self.compilation == self.COMPILATION_GRADER

    @staticmethod
    def _executable_filename(codenames, language):
        """Return the chosen executable name computed from the codenames.

        codenames ([str]): submission format or codename of submitted files,
            may contain %l.
        language (Language): the programming language of the submission.

        return (str): a deterministic executable name.

        """
        name =  "_".join(sorted(codename.replace(".%l", "")
                                for codename in codenames))
        return name + language.executable_extension
    
    def compile(self, job, file_cacher):
        """See TaskType.compile."""
        # No compilation needed.
        job.success = True
        job.compilation_success = True
        job.text = [N_("No compilation needed")]
        job.plus = {}

    def evaluate(self, job, file_cacher):
        """See TaskType.evaluate."""

        # Prepare the execution
        # executable_filename = next(iter(job.executables.keys()))
        # logger.info(str(executable_filename))

        filenames_and_digests_to_get = {}
        
        # User's submitted file(s) (full copy).
        for codename, file_ in job.files.items():
            filename = codename
            filenames_and_digests_to_get[filename] = file_.digest
        # Any other useful manager (full copy).
        for filename, manager in job.managers.items():
            filenames_and_digests_to_get[filename] = manager.digest
        
        # Check which redirect we need to perform, and in case we don't
        # manage the output via redirect, the submission needs to be able
        # to write on it.
        files_allowing_write = ["."]
        stdin_redirect = None
        stdout_redirect = self._actual_output

        # Create the sandbox
        sandbox = create_sandbox(file_cacher, name="evaluate")
        #sandbox.add_mapped_directory("/lib", "/lib", options="ro")
        #sandbox.add_mapped_directory("/lib64", "/lib64", options="ro")
        #sandbox.add_mapped_directory("/usr", "/usr", options="ro")
        #sandbox.add_mapped_directory("/usr/bin", "/usr/bin", options="ro")
        #sandbox.add_mapped_directory("/usr/lib", "/usr/lib", options="ro")
        job.sandboxes.append(sandbox.get_root_path())
        executables_to_get = {
            "judge.sh": job.input
        }

        # Put the required files into the sandbox
        for filename, digest in executables_to_get.items():
            sandbox.create_file_from_storage(filename, digest, executable=True)
        for filename, digest in filenames_and_digests_to_get.items():
            sandbox.create_file_from_storage(filename, digest)

        # read judge.sh from sandbox (caution! no limit on read file size)
        judge_cmds = sandbox.get_file_to_string("judge.sh", maxlen=None)
        judge_cmds = judge_cmds.decode("utf-8")
        commands = []
        for cmd in judge_cmds.splitlines():
            if cmd.startswith('ALLOW_FILE='):
                #files = cmd[len("ALLOW_FILE="):].split(",")
                #files_allowing_write += files
                pass
            else:
                commands.append(cmd.split())

        # in order to make gcc work, we need multiprocess
        # Actually performs the execution
        sandbox.allow_writing_all()
        box_success, evaluation_success, stats = evaluation_step(
            sandbox,
            commands,
            job.time_limit,
            job.memory_limit,
            writable_files=files_allowing_write,
            stdin_redirect=stdin_redirect,
            stdout_redirect=stdout_redirect,
            multiprocess=True)

        outcome = None
        text = None

        # Error in the sandbox: nothing to do!
        if not box_success:
            pass

        # Contestant's error: the marks won't be good
        elif not evaluation_success:
            outcome = 0.0
            text = human_evaluation_message(stats)
            if job.get_output:
                job.user_output = None

        # Otherwise, advance to checking the solution
        else:

            # Check that the output file was created
            if not sandbox.file_exists(self._actual_output):
                outcome = 0.0
                text = [N_("Evaluation didn't produce file %s"),
                        self._actual_output]
                if job.get_output:
                    job.user_output = None

            else:
                # If asked so, put the output file into the storage.
                if job.get_output:
                    job.user_output = sandbox.get_file_to_storage(
                        self._actual_output,
                        "Output file in job %s" % job.info,
                        trunc_len=100 * 1024)

                # If just asked to execute, fill text and set dummy outcome.
                if job.only_execution:
                    outcome = 0.0
                    text = [N_("Execution completed successfully")]

                # Otherwise evaluate the output file.
                else:
                    box_success, outcome, text = eval_output(
                        file_cacher, job,
                        self.CHECKER_CODENAME
                        if self._uses_checker() else None,
                        user_output_path=sandbox.relative_path(
                            self._actual_output),
                        user_output_filename=self.output_filename)

        # Fill in the job with the results.
        job.success = box_success
        job.outcome = str(outcome) if outcome is not None else None
        job.text = text
        job.plus = stats

        delete_sandbox(sandbox, job.success, job.keep_sandbox)
