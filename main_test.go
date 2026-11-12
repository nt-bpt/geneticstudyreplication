package main

import (
	"context"
	"os"
	"path/filepath"
	"testing"
)

// Every pipeline's skills must load, including the underscore-named ones.
func TestPipelinesLoad(t *testing.T) {
	for _, name := range []string{
		"ghost-ancestry-pipeline", "psi-genetics-pipeline",
		"striatum-project", "trio-pipeline",
	} {
		t.Run(name, func(t *testing.T) {
			p, err := loadPipeline(name, defaultAgentDir)
			if err != nil {
				t.Fatal(err)
			}
			if _, err := readInstruction(p); err != nil {
				t.Fatal(err)
			}
			src := newLooseSource(os.DirFS(p.skillsDir))
			fms, err := src.ListFrontmatters(context.Background())
			if err != nil || len(fms) == 0 {
				t.Fatalf("skills: %d, err: %v", len(fms), err)
			}
			for _, fm := range fms {
				if _, err := src.LoadInstructions(context.Background(), fm.Name); err != nil {
					t.Error(err)
				}
				if _, err := src.LoadResource(context.Background(), fm.Name, "../../x"); err == nil {
					t.Error("path traversal accepted")
				}
			}
		})
	}
}

func TestRunScript(t *testing.T) {
	dir := t.TempDir()
	skillDir := filepath.Join(dir, ".agent", "skills", "s1")
	if err := os.MkdirAll(skillDir, 0o755); err != nil {
		t.Fatal(err)
	}
	script := "echo \"root=$PIPELINE_ROOT cwd=$(pwd) arg=$1\"; echo oops >&2; exit 3\n"
	if err := os.WriteFile(filepath.Join(skillDir, "run.sh"), []byte(script), 0o644); err != nil {
		t.Fatal(err)
	}
	p := &pipeline{name: "x", dir: dir, root: dir, skillsDir: filepath.Join(dir, ".agent", "skills")}

	res := p.runScript(context.Background(), runScriptArgs{SkillName: "s1", FilePath: "run.sh", Args: []string{"a"}})
	if res.Status != "error" || res.ExitCode != 3 || res.Stderr != "oops\n" || res.Stdout == "" {
		t.Errorf("unexpected result: %+v", res)
	}

	no := false
	res = p.runScript(context.Background(), runScriptArgs{SkillName: "s1", FilePath: "run.sh", ReturnOutput: &no})
	if res.Stdout != "" || res.Stderr != "" {
		t.Errorf("output not suppressed: %+v", res)
	}

	for _, bad := range []runScriptArgs{
		{SkillName: "s1", FilePath: "../../../etc/passwd"},
		{SkillName: "s1", FilePath: "/etc/passwd"},
		{SkillName: "../s1", FilePath: "run.sh"},
		{SkillName: "nope", FilePath: "run.sh"},
		{SkillName: "s1", FilePath: "."},
	} {
		if r := p.runScript(context.Background(), bad); r.Status != "error" || r.Error == "" {
			t.Errorf("%+v accepted: %+v", bad, r)
		}
	}
}
