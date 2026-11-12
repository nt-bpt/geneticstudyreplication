package main

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"io/fs"
	"path"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"

	"google.golang.org/adk/v2/tool/skilltoolset/skill"
)

// looseSource reads skills from <dir>/<skill>/SKILL.md like
// skill.NewFileSystemSource, but does not enforce the agentskills.io naming
// rule (lowercase letters, digits and hyphens). The personal-pipeline and
// trio-pipeline skills are named like "03_align_fastq", which the strict
// source rejects. The skill name must still equal its folder name.
type looseSource struct {
	fsys fs.FS
}

var _ skill.Source = looseSource{}

func newLooseSource(fsys fs.FS) skill.Source { return looseSource{fsys: fsys} }

func (s looseSource) ListFrontmatters(ctx context.Context) ([]*skill.Frontmatter, error) {
	entries, err := fs.ReadDir(s.fsys, ".")
	if err != nil {
		return nil, err
	}
	var out []*skill.Frontmatter
	for _, e := range entries {
		if !e.IsDir() {
			continue
		}
		if _, err := fs.Stat(s.fsys, path.Join(e.Name(), "SKILL.md")); err != nil {
			continue // not a skill folder
		}
		fm, _, err := s.load(e.Name())
		if err != nil {
			return nil, err
		}
		out = append(out, fm)
	}
	return out, nil
}

func (s looseSource) LoadFrontmatter(ctx context.Context, name string) (*skill.Frontmatter, error) {
	fm, _, err := s.load(name)
	return fm, err
}

func (s looseSource) LoadInstructions(ctx context.Context, name string) (string, error) {
	_, body, err := s.load(name)
	return body, err
}

func (s looseSource) ListResources(ctx context.Context, name, subpath string) ([]string, error) {
	if err := checkSkillName(name); err != nil {
		return nil, err
	}
	if subpath == "" {
		subpath = "."
	}
	root := path.Join(name, subpath)
	if !fs.ValidPath(root) {
		return nil, fmt.Errorf("%w: %q", skill.ErrInvalidResourcePath, subpath)
	}
	var out []string
	err := fs.WalkDir(s.fsys, root, func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		rel := strings.TrimPrefix(p, name+"/")
		if !d.IsDir() && rel != "SKILL.md" {
			out = append(out, rel)
		}
		return nil
	})
	if err != nil {
		if fs.ValidPath(root) {
			if _, statErr := fs.Stat(s.fsys, root); statErr != nil {
				return nil, nil // no such sub-folder: no resources
			}
		}
		return nil, err
	}
	sort.Strings(out)
	return out, nil
}

func (s looseSource) LoadResource(ctx context.Context, name, resourcePath string) (io.ReadCloser, error) {
	if err := checkSkillName(name); err != nil {
		return nil, err
	}
	p := path.Join(name, resourcePath)
	if !fs.ValidPath(p) || !strings.HasPrefix(p, name+"/") {
		return nil, fmt.Errorf("%w: %q", skill.ErrInvalidResourcePath, resourcePath)
	}
	f, err := s.fsys.Open(p)
	if err != nil {
		return nil, fmt.Errorf("%w: %q", skill.ErrResourceNotFound, resourcePath)
	}
	return f, nil
}

func (s looseSource) load(name string) (*skill.Frontmatter, string, error) {
	if err := checkSkillName(name); err != nil {
		return nil, "", err
	}
	raw, err := fs.ReadFile(s.fsys, path.Join(name, "SKILL.md"))
	if err != nil {
		return nil, "", fmt.Errorf("%w: %q", skill.ErrSkillNotFound, name)
	}
	fm, body, err := splitFrontmatter(raw)
	if err != nil {
		return nil, "", fmt.Errorf("%w: %s: %v", skill.ErrInvalidFrontmatter, name, err)
	}
	if fm.Name != name {
		return nil, "", fmt.Errorf("%w: %s: name %q does not match folder", skill.ErrInvalidFrontmatter, name, fm.Name)
	}
	if strings.TrimSpace(fm.Description) == "" {
		return nil, "", fmt.Errorf("%w: %s: description is required", skill.ErrInvalidFrontmatter, name)
	}
	return fm, body, nil
}

func checkSkillName(name string) error {
	if name == "" || name == "." || name == ".." || strings.ContainsAny(name, `/\`) {
		return fmt.Errorf("%w: %q", skill.ErrInvalidSkillName, name)
	}
	return nil
}

// splitFrontmatter splits "---\n<yaml>\n---\n<markdown>" into its parts.
func splitFrontmatter(raw []byte) (*skill.Frontmatter, string, error) {
	text := strings.ReplaceAll(string(bytes.TrimPrefix(raw, []byte("\xef\xbb\xbf"))), "\r\n", "\n")
	rest, ok := strings.CutPrefix(text, "---\n")
	if !ok {
		return nil, "", fmt.Errorf("missing opening ---")
	}
	header, body, ok := strings.Cut(rest, "\n---")
	if !ok {
		return nil, "", fmt.Errorf("missing closing ---")
	}
	var fm skill.Frontmatter
	if err := yaml.Unmarshal([]byte(header), &fm); err != nil {
		return nil, "", err
	}
	_, body, _ = strings.Cut(body, "\n") // rest of the closing --- line
	return &fm, body, nil
}
