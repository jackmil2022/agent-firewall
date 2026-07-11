const assert = require("node:assert/strict");
const path = require("node:path");
const test = require("node:test");

const { pythonCommand } = require("./workspace");

test("development backend uses the project virtualenv, not the selected workspace", () => {
  const originalPython = process.env.PYTHON;
  const originalResourcesPath = process.resourcesPath;
  const workspace = path.join(__dirname, "test-fixtures", "workspace-without-venv");
  const expected = process.platform === "win32"
    ? path.resolve(__dirname, "..", ".venv", "Scripts", "python.exe")
    : path.resolve(__dirname, "..", ".venv", "bin", "python");

  delete process.env.PYTHON;
  delete process.resourcesPath;
  try {
    assert.equal(pythonCommand(workspace), expected);
  } finally {
    if (originalPython === undefined) delete process.env.PYTHON;
    else process.env.PYTHON = originalPython;
    if (originalResourcesPath === undefined) delete process.resourcesPath;
    else process.resourcesPath = originalResourcesPath;
  }
});
