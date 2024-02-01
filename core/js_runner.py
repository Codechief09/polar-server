from nodejs import node
import subprocess
import tempfile
import os

# this is temporary code. you should fix in the future
def run_js(script, return_variable_name="output"):
    # disable console.log
    script = "process.env.TZ = \"Asia/Tokyo\";console.log = function() {};\n" + script
    # export output varible
    script += "\nprocess.stdout.write(" + return_variable_name + ".toString());"
    # create temporary file on temp folder
    temp_file = tempfile.NamedTemporaryFile(delete=False)
    temp_file.write(script.encode("utf8"))
    temp_file.close()

    # run js
    proc = node.Popen([temp_file.name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # wait for the process to finish
    proc.wait()
    # get stdout and stderr
    stdout, stderr = proc.stdout.read(), proc.stderr.read()

    if len(stderr) > 0:
        print(stderr.decode("utf-8"))
        raise Exception("Error in js runner")

    # delete temporary file
    os.remove(temp_file.name)
    ret = stdout.decode("utf-8")
    return ret