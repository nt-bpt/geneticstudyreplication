// Command main runs one of the pipelines in this repository as an ADK (Go)
// agent backed by a local Ollama model.
//
// Run it from the repository root, e.g.
//
//	PIPELINE=ghost-ancestry-pipeline go run . console
//	PIPELINE=trio-pipeline go run . web api webui
//
// Settings (environment variables):
//
//	PIPELINE         folder name of the pipeline to run (required), e.g.
//	                 ghost-ancestry-pipeline, trio-pipeline,
//	                 psi-genetics-pipeline, striatum-project.
//	PIPELINE_AGENT   folder name of the agent folder inside the pipeline that
//	                 holds skills/ (default ".agent").
//	OLLAMA_MODEL     Ollama model name (default "muse-glimmer:30b-q4_K_M"). It must support
//	                 tool calling.
//	OLLAMA_HOST      Ollama server (default "http://localhost:11434").
//
// What the agent gets:
//  1. every skill in <PIPELINE>/<PIPELINE_AGENT>/skills (list_skills,
//     load_skill, load_skill_resource),
//  2. a run_skill_script tool that runs a script of a skill on this machine,
//     from the pipeline folder (the folder that holds .agent/skills/),
//  3. the pipeline's AGENTS.md (in the pipeline folder) as its instruction, passed through
//     an instruction provider so ADK does not apply {placeholder} templating
//     to it.
//
// Scripts inherit this process's environment plus PROC_ROOT (the pipeline
// folder) and PIPELINE_ROOT (the pipeline's repo/ folder when it has one,
// otherwise the pipeline folder).
package main

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"log"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/google/jsonschema-go/jsonschema"

	"google.golang.org/adk/v2/agent"
	"google.golang.org/adk/v2/agent/llmagent"
	"google.golang.org/adk/v2/cmd/launcher"
	"google.golang.org/adk/v2/cmd/launcher/full"
	"google.golang.org/adk/v2/model"
	"google.golang.org/adk/v2/model/openaimodel"
	"google.golang.org/adk/v2/tool"
	"google.golang.org/adk/v2/tool/functiontool"
	"google.golang.org/adk/v2/tool/skilltoolset"
)

const (
	defaultAgentDir   = ".agent"
	defaultOllamaHost = "http://localhost:11434"
	defaultModel      = "muse-glimmer:30b-q4_K_M"

	// Every pipeline call returns in seconds (long work runs in the
	// background), so the timeout only guards against a stuck call.
	scriptTimeout = 600 * time.Second
	// How long to wait for output pipes to close after a script exits; a
	// background child that inherited them must not block the tool call.
	scriptWaitDelay = 5 * time.Second
	maxOutputBytes  = 32 * 1024
)

// instructionFile sits in the root of every pipeline folder.
const instructionFile = "AGENTS.md"

// pipeline describes the selected pipeline folder.
type pipeline struct {
	name      string // folder name, e.g. "trio-pipeline"
	dir       string // absolute path of the pipeline folder (script cwd)
	root      string // PIPELINE_ROOT: <dir>/repo if present, else dir
	skillsDir string // <dir>/<agent folder>/skills
}

func main() {
	ctx := context.Background()

	p, err := loadPipeline(os.Getenv("PIPELINE"), envOr("PIPELINE_AGENT", defaultAgentDir))
	if err != nil {
		log.Fatal(err)
	}

	instruction, err := readInstruction(p)
	if err != nil {
		log.Fatal(err)
	}

	llm, err := newOllamaModel(ctx, envOr("OLLAMA_MODEL", defaultModel), envOr("OLLAMA_HOST", defaultOllamaHost))
	if err != nil {
		log.Fatalf("create model: %v", err)
	}

	source := newLooseSource(os.DirFS(p.skillsDir))
	// Fail early on a malformed skill instead of on the first model request.
	skills, err := source.ListFrontmatters(ctx)
	if err != nil {
		log.Fatalf("load skills from %s: %v", p.skillsDir, err)
	}
	log.Printf("pipeline %q: %d skills from %s", p.name, len(skills), p.skillsDir)

	skillToolset, err := skilltoolset.New(ctx, skilltoolset.Config{Source: source})
	if err != nil {
		log.Fatalf("create skill toolset: %v", err)
	}

	runScript, err := newRunSkillScriptTool(p)
	if err != nil {
		log.Fatalf("create run_skill_script tool: %v", err)
	}

	rootAgent, err := llmagent.New(llmagent.Config{
		Name:        agentName(p.name),
		Model:       llm,
		Description: fmt.Sprintf("Runs the %s skills in order.", p.name),
		// The instruction is plain text that must reach the model unchanged;
		// InstructionProvider skips {placeholder} state templating.
		InstructionProvider: func(agent.ReadonlyContext) (string, error) { return instruction, nil },
		Tools:               []tool.Tool{runScript},
		Toolsets:            []tool.Toolset{skillToolset},
	})
	if err != nil {
		log.Fatalf("create agent: %v", err)
	}

	l := full.NewLauncher()
	if err := l.Execute(ctx, &launcher.Config{AgentLoader: agent.NewSingleLoader(rootAgent)}, os.Args[1:]); err != nil {
		log.Fatalf("run failed: %v\n\n%s", err, l.CommandLineSyntax())
	}
}

// loadPipeline resolves the pipeline and agent folder names, which are plain
// folder names relative to the working directory.
func loadPipeline(name, agentFolder string) (*pipeline, error) {
	if err := checkFolderName("PIPELINE", name); err != nil {
		return nil, err
	}
	if err := checkFolderName("PIPELINE_AGENT", agentFolder); err != nil {
		return nil, err
	}
	cwd, err := os.Getwd()
	if err != nil {
		return nil, err
	}
	dir := filepath.Join(cwd, name)
	if !isDir(dir) {
		return nil, fmt.Errorf("PIPELINE=%q: no folder %s (run from the repository root; available: %s)",
			name, dir, strings.Join(listPipelines(cwd), ", "))
	}
	skillsDir := filepath.Join(dir, agentFolder, "skills")
	if !isDir(skillsDir) {
		return nil, fmt.Errorf("PIPELINE_AGENT=%q: no skills folder %s", agentFolder, skillsDir)
	}
	root := dir
	if r := filepath.Join(dir, "repo"); isDir(r) {
		root = r
	}
	return &pipeline{name: name, dir: dir, root: root, skillsDir: skillsDir}, nil
}

func checkFolderName(setting, v string) error {
	if v == "" {
		return fmt.Errorf("%s is not set: set it to a pipeline folder name", setting)
	}
	if v == "." || v == ".." || strings.ContainsAny(v, `/\`) {
		return fmt.Errorf("%s=%q must be a plain folder name", setting, v)
	}
	return nil
}

// listPipelines returns the sub-folders of dir that contain an agent folder,
// to make a wrong PIPELINE value easy to fix.
func listPipelines(dir string) []string {
	entries, _ := os.ReadDir(dir)
	var names []string
	for _, e := range entries {
		if e.IsDir() && isDir(filepath.Join(dir, e.Name(), defaultAgentDir, "skills")) {
			names = append(names, e.Name())
		}
	}
	return names
}

func readInstruction(p *pipeline) (string, error) {
	b, err := os.ReadFile(filepath.Join(p.dir, instructionFile))
	if err != nil {
		return "", fmt.Errorf("pipeline %q: %w", p.name, err)
	}
	return string(b), nil
}

var nonIdent = regexp.MustCompile(`[^A-Za-z0-9_]+`)

// agentName turns a folder name into a valid ADK agent name (an identifier).
func agentName(folder string) string {
	n := strings.Trim(nonIdent.ReplaceAllString(folder, "_"), "_")
	if n == "" || (n[0] >= '0' && n[0] <= '9') {
		n = "p_" + n
	}
	return n + "_agent"
}

// newOllamaModel talks to Ollama through its OpenAI-compatible Chat
// Completions endpoint, which supports tool calling.
func newOllamaModel(ctx context.Context, modelName, host string) (model.LLM, error) {
	if !strings.Contains(host, "://") {
		host = "http://" + host // OLLAMA_HOST is often just host:port
	}
	return openaimodel.NewModel(ctx, modelName, &openaimodel.ClientConfig{
		APIKey:  "ollama", // required by the client, ignored by Ollama
		BaseURL: strings.TrimRight(host, "/") + "/v1",
		API:     openaimodel.APIChatCompletions,
	})
}

type runScriptArgs struct {
	SkillName    string   `json:"skill_name"`
	FilePath     string   `json:"file_path"`
	Args         []string `json:"args,omitempty"`
	ReturnOutput *bool    `json:"return_output,omitempty"`
}

type runScriptResult struct {
	Status   string `json:"status"` // "success" or "error"
	ExitCode int    `json:"exit_code"`
	Stdout   string `json:"stdout,omitempty"`
	Stderr   string `json:"stderr,omitempty"`
	Error    string `json:"error,omitempty"`
}

func newRunSkillScriptTool(p *pipeline) (tool.Tool, error) {
	str := func(desc string) *jsonschema.Schema { return &jsonschema.Schema{Type: "string", Description: desc} }
	return functiontool.New(functiontool.Config{
		Name: "run_skill_script",
		Description: "Runs a script that belongs to a skill (a .py or .sh file in the skill folder) and returns its " +
			"exit code, stdout and stderr. Use the skill_name and file_path given in the skill's instructions.",
		InputSchema: &jsonschema.Schema{
			Type: "object",
			Properties: map[string]*jsonschema.Schema{
				"skill_name": str("Name of the skill that owns the script."),
				"file_path":  str("Path of the script relative to the skill folder, e.g. scripts/03-align-reads.py."),
				"args": {
					Type:        "array",
					Items:       &jsonschema.Schema{Type: "string"},
					Description: "Optional command-line arguments for the script.",
				},
				"return_output": {
					Type:        "boolean",
					Description: "Set to false to leave stdout and stderr out of the result. Defaults to true.",
				},
			},
			Required: []string{"skill_name", "file_path"},
		},
	}, func(ctx agent.Context, in runScriptArgs) (runScriptResult, error) {
		return p.runScript(ctx, in), nil
	})
}

// runScript runs a skill script. Failures are returned in the result (not as
// Go errors) so the model can read them and react.
func (p *pipeline) runScript(ctx context.Context, in runScriptArgs) runScriptResult {
	fail := func(format string, a ...any) runScriptResult {
		return runScriptResult{Status: "error", ExitCode: -1, Error: fmt.Sprintf(format, a...)}
	}

	if err := checkFolderName("skill_name", in.SkillName); err != nil {
		return fail("%v", err)
	}
	skillDir := filepath.Join(p.skillsDir, in.SkillName)
	if !isDir(skillDir) {
		return fail("unknown skill %q", in.SkillName)
	}
	script := filepath.Join(skillDir, filepath.FromSlash(in.FilePath))
	if rel, err := filepath.Rel(skillDir, script); err != nil || rel == "." || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return fail("file_path %q must be a file inside the skill folder", in.FilePath)
	}
	if st, err := os.Stat(script); err != nil || st.IsDir() {
		return fail("script %q not found in skill %q", in.FilePath, in.SkillName)
	}

	var cmd *exec.Cmd
	ctx, cancel := context.WithTimeout(ctx, scriptTimeout)
	defer cancel()
	switch strings.ToLower(filepath.Ext(script)) {
	case ".py":
		cmd = exec.CommandContext(ctx, "python3", append([]string{script}, in.Args...)...)
	case ".sh":
		cmd = exec.CommandContext(ctx, "bash", append([]string{script}, in.Args...)...)
	default:
		cmd = exec.CommandContext(ctx, script, in.Args...)
	}
	cmd.Dir = p.dir
	cmd.Env = append(os.Environ(), "PROC_ROOT="+p.dir, "PIPELINE_ROOT="+p.root)
	cmd.WaitDelay = scriptWaitDelay
	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr

	res := runScriptResult{Status: "success"}
	if err := cmd.Run(); err != nil {
		res.Status = "error"
		res.ExitCode = -1
		var ee *exec.ExitError
		if errors.As(err, &ee) {
			res.ExitCode = ee.ExitCode()
		} else {
			res.Error = err.Error()
		}
		if ctx.Err() != nil {
			res.Error = fmt.Sprintf("script did not finish within %s", scriptTimeout)
		}
	}
	if in.ReturnOutput == nil || *in.ReturnOutput {
		res.Stdout, res.Stderr = tail(stdout.String()), tail(stderr.String())
	}
	return res
}

// tail keeps the end of s, where scripts report their result and errors.
func tail(s string) string {
	if len(s) <= maxOutputBytes {
		return s
	}
	return "...[truncated]...\n" + s[len(s)-maxOutputBytes:]
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func isDir(path string) bool {
	st, err := os.Stat(path)
	return err == nil && st.IsDir()
}
