import { createFileRoute } from '@tanstack/react-router'
import { useState, useRef, useEffect, useCallback } from 'react'
import { useMutation } from '@tanstack/react-query'
import {
  Loader2,
  Sparkles,
  RefreshCw,
  Link2,
  ChevronDown,
  Copy,
  Check,
  Zap,
  Settings2,
  AlertCircle,
  Pencil,
  X,
  RotateCcw,
  MessageSquarePlus,
  Trash2
} from 'lucide-react'
import { api, inspireWithProgress, type InspireRequest, type InspireResponse, type RegenerateRequest, type ProgressEvent } from '~/lib/api'
import { Button } from '~/components/ui/button'
import { Input } from '~/components/ui/input'
import { Label } from '~/components/ui/label'
import { Textarea } from '~/components/ui/textarea'
import { Checkbox } from '~/components/ui/checkbox'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '~/components/ui/select'
import { Card, CardContent } from '~/components/ui/card'
import { Alert, AlertDescription } from '~/components/ui/alert'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '~/components/ui/tooltip'
import { cn } from '~/lib/utils'

// Annotation types for inline text suggestions
interface Annotation {
  id: string
  start: number
  end: number
  text: string
  suggestion: string
}

interface TextSegment {
  text: string
  annotation?: Annotation
  start: number
  end: number
}

export const Route = createFileRoute('/')({
  component: InspirePage,
})

function InspirePage() {
  const [result, setResult] = useState<InspireResponse | null>(null)
  const [regeneratedProposals, setRegeneratedProposals] = useState<InspireResponse['proposals'] | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [isGenerating, setIsGenerating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [currentProgress, setCurrentProgress] = useState<ProgressEvent | null>(null)
  const resultsRef = useRef<HTMLDivElement>(null)

  const [formData, setFormData] = useState<InspireRequest>({
    username: '',
    tweet_url: '',
    content_type: 'all',
    thread_count: 5,
    vibe: '',
    context: '',
    profile_file: '',
    deep_research: false,
    use_full_content: false,
  })

  const [regenerateData, setRegenerateData] = useState<Omit<RegenerateRequest, 'research_id'>>({
    content_type: 'all',
    thread_count: 5,
    vibe: '',
    context: '',
    suggestions: '',
  })

  const regenerateMutation = useMutation({
    mutationFn: (data: RegenerateRequest) => api.regenerate({
      ...data,
      vibe: data.vibe || undefined,
      context: data.context || undefined,
      suggestions: data.suggestions || undefined,
    }),
    onSuccess: (response) => {
      setRegeneratedProposals(response.proposals)
    },
  })

  // Scroll to results when they appear
  useEffect(() => {
    if (result && resultsRef.current) {
      resultsRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [result])

  const handleProgressUpdate = useCallback((event: ProgressEvent) => {
    setCurrentProgress(event)
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsGenerating(true)
    setError(null)
    setResult(null)
    setCurrentProgress(null)
    setRegeneratedProposals(null)

    try {
      const response = await inspireWithProgress(
        {
          ...formData,
          vibe: formData.vibe || undefined,
          context: formData.context || undefined,
          profile_file: formData.profile_file || undefined,
        },
        handleProgressUpdate
      )

      setResult(response)
      setRegenerateData({
        content_type: formData.content_type,
        thread_count: formData.thread_count,
        vibe: formData.vibe || '',
        context: formData.context || '',
        suggestions: '',
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setIsGenerating(false)
    }
  }

  const handleRegenerate = (e: React.FormEvent) => {
    e.preventDefault()
    if (!result?.research_id) return
    regenerateMutation.mutate({
      research_id: result.research_id,
      ...regenerateData,
    })
  }

  // Handler for inline regeneration from proposal cards
  const handleInlineRegenerate = useCallback((suggestions: string, contentType: string) => {
    if (!result?.research_id) return
    regenerateMutation.mutate({
      research_id: result.research_id,
      content_type: contentType,
      thread_count: formData.thread_count,
      vibe: formData.vibe || '',
      context: formData.context || '',
      suggestions,
    })
  }, [result?.research_id, formData.thread_count, formData.vibe, formData.context, regenerateMutation])

  const displayProposals = regeneratedProposals || result?.proposals

  return (
    <div className="space-y-8">
      {/* Hero Input Section */}
      <div className="text-center space-y-4 pt-8">
        <h2 className="text-4xl font-bold tracking-tight bg-gradient-to-r from-foreground to-foreground/60 bg-clip-text text-transparent">
          Get inspired by any tweet
        </h2>
        <p className="text-lg text-muted-foreground max-w-xl mx-auto">
          Paste a tweet URL and let AI generate engaging content in your unique voice
        </p>
      </div>

      {/* Main Form */}
      <Card className="border-border/50 shadow-xl shadow-black/5">
        <CardContent className="p-6 space-y-6">
          <form onSubmit={handleSubmit} className="space-y-6">
            {/* Primary Inputs */}
            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="tweet_url" className="text-base font-medium">
                  Tweet URL
                </Label>
                <div className="relative">
                  <Link2 className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    id="tweet_url"
                    type="url"
                    value={formData.tweet_url}
                    onChange={(e) => setFormData({ ...formData, tweet_url: e.target.value })}
                    placeholder="https://twitter.com/user/status/123456789..."
                    className="pl-10 h-12 text-base"
                    required
                    disabled={isGenerating}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="username" className="text-sm">
                    Your Twitter username
                  </Label>
                  <Input
                    id="username"
                    value={formData.username}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    placeholder="username (without @)"
                    className="h-11"
                    required
                    disabled={isGenerating}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="content_type" className="text-sm">
                    Content type
                  </Label>
                  <Select
                    value={formData.content_type}
                    onValueChange={(value) => setFormData({ ...formData, content_type: value })}
                    disabled={isGenerating}
                  >
                    <SelectTrigger className="h-11">
                      <SelectValue placeholder="Select type" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="quote">Quote Tweet</SelectItem>
                      <SelectItem value="tweet">Standalone Tweet</SelectItem>
                      <SelectItem value="reply">Reply</SelectItem>
                      <SelectItem value="thread">Thread</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            {/* Advanced Options Toggle */}
            <button
              type="button"
              onClick={() => setShowAdvanced(!showAdvanced)}
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
              disabled={isGenerating}
            >
              <Settings2 className="h-4 w-4" />
              Advanced options
              <ChevronDown className={cn(
                "h-4 w-4 transition-transform",
                showAdvanced && "rotate-180"
              )} />
            </button>

            {/* Advanced Options */}
            {showAdvanced && (
              <div className="space-y-4 pt-2 animate-fade-in">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="vibe" className="text-sm">
                      Vibe / Tone
                    </Label>
                    <Input
                      id="vibe"
                      value={formData.vibe}
                      onChange={(e) => setFormData({ ...formData, vibe: e.target.value })}
                      placeholder="e.g., witty, professional, casual..."
                      className="h-11"
                      disabled={isGenerating}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="thread_count" className="text-sm">
                      Thread length (if thread)
                    </Label>
                    <Input
                      type="number"
                      id="thread_count"
                      value={formData.thread_count}
                      onChange={(e) => setFormData({ ...formData, thread_count: parseInt(e.target.value) || 5 })}
                      min={2}
                      max={20}
                      className="h-11"
                      disabled={isGenerating}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="context" className="text-sm">
                    Additional context
                  </Label>
                  <Textarea
                    id="context"
                    value={formData.context}
                    onChange={(e) => setFormData({ ...formData, context: e.target.value })}
                    placeholder="Any specific angle or context you want to add..."
                    rows={2}
                    className="resize-none"
                    disabled={isGenerating}
                  />
                </div>

                <div className="flex flex-wrap gap-6 pt-2">
                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="deep_research"
                      checked={formData.deep_research}
                      onCheckedChange={(checked) => setFormData({ ...formData, deep_research: checked === true })}
                      disabled={isGenerating}
                    />
                    <Label htmlFor="deep_research" className="text-sm cursor-pointer">
                      Deep research mode
                    </Label>
                  </div>

                  <div className="flex items-center space-x-2">
                    <Checkbox
                      id="use_full_content"
                      checked={formData.use_full_content}
                      onCheckedChange={(checked) => setFormData({ ...formData, use_full_content: checked === true })}
                      disabled={isGenerating}
                    />
                    <Label htmlFor="use_full_content" className="text-sm cursor-pointer">
                      Use full content for research
                    </Label>
                  </div>
                </div>
              </div>
            )}

            {/* Submit Button */}
            <Button
              type="submit"
              disabled={isGenerating}
              className="w-full h-12 text-base font-medium"
              size="lg"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  {currentProgress?.message || 'Generating content...'}
                </>
              ) : (
                <>
                  <Sparkles className="mr-2 h-5 w-5" />
                  Generate Content
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Error State */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Results */}
      {result && (
        <div ref={resultsRef} className="space-y-6 animate-fade-in">
          {/* Original Tweet */}
          <OriginalTweet tweet={result.original_tweet} />

          {/* Generated Content */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Zap className="h-5 w-5 text-primary" />
              Generated Content
            </h3>

            {displayProposals?.quote?.map((proposal, i) => (
              <ProposalCard
                key={`quote-${i}`}
                type="Quote Tweet"
                content={proposal.content}
                contentType="quote"
                onRegenerate={handleInlineRegenerate}
                isRegenerating={regenerateMutation.isPending}
              />
            ))}

            {displayProposals?.tweet?.map((proposal, i) => (
              <ProposalCard
                key={`tweet-${i}`}
                type="Tweet"
                content={proposal.content}
                contentType="tweet"
                onRegenerate={handleInlineRegenerate}
                isRegenerating={regenerateMutation.isPending}
              />
            ))}

            {displayProposals?.reply?.map((proposal, i) => (
              <ProposalCard
                key={`reply-${i}`}
                type="Reply"
                content={proposal.content}
                contentType="reply"
                onRegenerate={handleInlineRegenerate}
                isRegenerating={regenerateMutation.isPending}
              />
            ))}

            {displayProposals?.thread?.map((proposal, i) => (
              <ThreadCard
                key={`thread-${i}`}
                content={proposal.content}
                onRegenerate={handleInlineRegenerate}
                isRegenerating={regenerateMutation.isPending}
              />
            ))}
          </div>

          {/* Quick Regenerate */}
          {result.research_id && (
            <Card className="border-dashed">
              <CardContent className="p-4">
                <form onSubmit={handleRegenerate} className="space-y-4">
                  <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground">
                    <RefreshCw className="h-4 w-4" />
                    Quick regenerate with different settings
                  </div>

                  <div className="flex flex-wrap gap-3">
                    <Select
                      value={regenerateData.content_type}
                      onValueChange={(value) => setRegenerateData({ ...regenerateData, content_type: value })}
                    >
                      <SelectTrigger className="w-40 h-9">
                        <SelectValue placeholder="Type" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="quote">Quote</SelectItem>
                        <SelectItem value="tweet">Tweet</SelectItem>
                        <SelectItem value="reply">Reply</SelectItem>
                        <SelectItem value="thread">Thread</SelectItem>
                      </SelectContent>
                    </Select>

                    <Input
                      value={regenerateData.vibe}
                      onChange={(e) => setRegenerateData({ ...regenerateData, vibe: e.target.value })}
                      placeholder="Different vibe..."
                      className="flex-1 min-w-[150px] h-9"
                    />

                    <Button
                      type="submit"
                      variant="secondary"
                      size="sm"
                      disabled={regenerateMutation.isPending}
                      className="h-9"
                    >
                      {regenerateMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <>
                          <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                          Regenerate
                        </>
                      )}
                    </Button>
                  </div>

                  <Input
                    value={regenerateData.suggestions}
                    onChange={(e) => setRegenerateData({ ...regenerateData, suggestions: e.target.value })}
                    placeholder="Suggestions: make it shorter, more technical, add humor..."
                    className="h-9 text-sm"
                  />
                </form>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  )
}

// Original Tweet Component
function OriginalTweet({ tweet }: { tweet: InspireResponse['original_tweet'] }) {
  return (
    <Card className="bg-card/50">
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-blue-400 to-blue-600 text-white font-bold">
            {tweet.author_username?.[0]?.toUpperCase() || '?'}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-semibold">@{tweet.author_username || 'unknown'}</span>
              <span className="text-xs text-muted-foreground">Original tweet</span>
            </div>
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{tweet.text}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// Helper function to split text into segments based on annotations
function getTextSegments(text: string, annotations: Annotation[]): TextSegment[] {
  if (annotations.length === 0) {
    return [{ text, start: 0, end: text.length }]
  }

  // Sort annotations by start position
  const sorted = [...annotations].sort((a, b) => a.start - b.start)
  const segments: TextSegment[] = []
  let currentPos = 0

  for (const annotation of sorted) {
    // Add text before this annotation
    if (annotation.start > currentPos) {
      segments.push({
        text: text.slice(currentPos, annotation.start),
        start: currentPos,
        end: annotation.start,
      })
    }
    // Add the annotated segment
    segments.push({
      text: text.slice(annotation.start, annotation.end),
      annotation,
      start: annotation.start,
      end: annotation.end,
    })
    currentPos = annotation.end
  }

  // Add remaining text after last annotation
  if (currentPos < text.length) {
    segments.push({
      text: text.slice(currentPos),
      start: currentPos,
      end: text.length,
    })
  }

  return segments
}

// Format annotations for the API
function formatAnnotationsForAPI(annotations: Annotation[]): string {
  return annotations
    .map((a) => `For "${a.text}": ${a.suggestion}`)
    .join('\n')
}

// Edit mode types
type EditMode = 'annotate' | 'edit'

// Proposal Card Component with Annotation System and Live Edit
function ProposalCard({
  type,
  content,
  contentType,
  onRegenerate,
  isRegenerating
}: {
  type: string
  content: string | string[]
  contentType: string
  onRegenerate?: (suggestions: string, specificType: string) => void
  isRegenerating?: boolean
}) {
  const [copied, setCopied] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editMode, setEditMode] = useState<EditMode>('annotate')
  const [editedText, setEditedText] = useState('')
  const [annotations, setAnnotations] = useState<Annotation[]>([])
  const [showPopover, setShowPopover] = useState(false)
  const [popoverPosition, setPopoverPosition] = useState({ x: 0, y: 0 })
  const [selectedRange, setSelectedRange] = useState<{ start: number; end: number; text: string } | null>(null)
  const [suggestionInput, setSuggestionInput] = useState('')
  const textContainerRef = useRef<HTMLDivElement>(null)
  const originalText = Array.isArray(content) ? content.join('\n\n') : content

  const handleCopy = async () => {
    const textToCopy = editMode === 'edit' && editedText ? editedText : originalText
    await navigator.clipboard.writeText(textToCopy)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleEdit = () => {
    setIsEditing(true)
    setEditMode('annotate')
    setEditedText(originalText)
    setAnnotations([])
  }

  const handleCancel = () => {
    setIsEditing(false)
    setEditMode('annotate')
    setEditedText('')
    setAnnotations([])
    setShowPopover(false)
    setSelectedRange(null)
    setSuggestionInput('')
  }

  const handleRegenerate = () => {
    if (!onRegenerate) return

    if (editMode === 'annotate' && annotations.length > 0) {
      const suggestions = formatAnnotationsForAPI(annotations)
      onRegenerate(suggestions, contentType)
    } else if (editMode === 'edit' && editedText !== originalText) {
      const suggestions = `Improve based on this edited version: "${editedText}"`
      onRegenerate(suggestions, contentType)
    }

    setIsEditing(false)
    setAnnotations([])
    setEditedText('')
  }

  const canRegenerate = editMode === 'annotate'
    ? annotations.length > 0
    : editedText !== originalText

  const handleMouseUp = useCallback(() => {
    if (!isEditing || editMode !== 'annotate' || !textContainerRef.current) return

    const selection = window.getSelection()
    if (!selection || selection.isCollapsed || !selection.toString().trim()) {
      return
    }

    const selectedText = selection.toString().trim()
    const range = selection.getRangeAt(0)

    // Check if selection is within our text container
    if (!textContainerRef.current.contains(range.commonAncestorContainer)) {
      return
    }

    // Calculate the position within the original text
    const rangeText = range.toString()

    // Find the start position by looking at the selection's position relative to the container
    let startOffset = 0
    const treeWalker = document.createTreeWalker(
      textContainerRef.current,
      NodeFilter.SHOW_TEXT,
      null
    )

    let node: Node | null
    let found = false
    while ((node = treeWalker.nextNode())) {
      if (node === range.startContainer) {
        startOffset += range.startOffset
        found = true
        break
      }
      startOffset += (node.textContent?.length || 0)
    }

    if (!found) return

    const endOffset = startOffset + rangeText.length

    // Check for overlapping annotations
    const hasOverlap = annotations.some(
      (a) => (startOffset < a.end && endOffset > a.start)
    )
    if (hasOverlap) {
      selection.removeAllRanges()
      return
    }

    // Get position for popover
    const rect = range.getBoundingClientRect()
    const containerRect = textContainerRef.current.getBoundingClientRect()

    setPopoverPosition({
      x: rect.left - containerRect.left + rect.width / 2,
      y: rect.bottom - containerRect.top + 8,
    })
    setSelectedRange({ start: startOffset, end: endOffset, text: selectedText })
    setShowPopover(true)
    setSuggestionInput('')
  }, [isEditing, editMode, annotations])

  const handleAddAnnotation = () => {
    if (!selectedRange || !suggestionInput.trim()) return

    const newAnnotation: Annotation = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      start: selectedRange.start,
      end: selectedRange.end,
      text: selectedRange.text,
      suggestion: suggestionInput.trim(),
    }

    setAnnotations((prev) => [...prev, newAnnotation])
    setShowPopover(false)
    setSelectedRange(null)
    setSuggestionInput('')
    window.getSelection()?.removeAllRanges()
  }

  const handleRemoveAnnotation = (id: string) => {
    setAnnotations((prev) => prev.filter((a) => a.id !== id))
  }

  const segments = getTextSegments(originalText, annotations)

  return (
    <TooltipProvider delayDuration={200}>
      <Card className={cn(
        "group transition-all",
        isEditing ? "border-primary ring-1 ring-primary/20" : "hover:border-primary/30"
      )}>
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-2 mb-2">
            <span className="inline-block text-xs font-medium text-primary bg-primary/10 px-2 py-0.5 rounded">
              {type}
            </span>
            <div className="flex items-center gap-1">
              {isEditing ? (
                <>
                  {editMode === 'annotate' && annotations.length > 0 && (
                    <span className="text-xs text-muted-foreground mr-2">
                      {annotations.length} suggestion{annotations.length !== 1 ? 's' : ''}
                    </span>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCancel}
                    className="h-7 px-2 text-xs"
                  >
                    <X className="h-3 w-3 mr-1" />
                    Cancel
                  </Button>
                  <Button
                    variant="default"
                    size="sm"
                    onClick={handleRegenerate}
                    disabled={!canRegenerate || isRegenerating}
                    className="h-7 px-2 text-xs"
                  >
                    {isRegenerating ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <>
                        <RotateCcw className="h-3 w-3 mr-1" />
                        Regenerate
                      </>
                    )}
                  </Button>
                </>
              ) : (
                <>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleEdit}
                    className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Edit content"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleCopy}
                    className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Copy to clipboard"
                  >
                    {copied ? (
                      <Check className="h-3.5 w-3.5 text-green-500" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </>
              )}
            </div>
          </div>

          {isEditing && (
            <div className="mb-3 space-y-2">
              {/* Mode Toggle */}
              <div className="flex gap-1 p-0.5 bg-muted rounded-md w-fit">
                <button
                  onClick={() => setEditMode('annotate')}
                  className={cn(
                    "px-2.5 py-1 text-xs font-medium rounded transition-colors",
                    editMode === 'annotate'
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <MessageSquarePlus className="h-3 w-3 inline mr-1" />
                  Suggest
                </button>
                <button
                  onClick={() => setEditMode('edit')}
                  className={cn(
                    "px-2.5 py-1 text-xs font-medium rounded transition-colors",
                    editMode === 'edit'
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Pencil className="h-3 w-3 inline mr-1" />
                  Edit
                </button>
              </div>
              <p className="text-xs text-muted-foreground">
                {editMode === 'annotate'
                  ? '✨ Select text to add suggestions. Hover over highlights to see or remove them.'
                  : '✏️ Edit the text directly. Your changes will guide the AI regeneration.'}
              </p>
            </div>
          )}

          {isEditing && editMode === 'edit' ? (
            <Textarea
              value={editedText}
              onChange={(e) => setEditedText(e.target.value)}
              className="min-h-[100px] text-sm resize-none leading-relaxed"
              placeholder="Edit the content..."
            />
          ) : (
            <div
              ref={textContainerRef}
              className={cn(
                "whitespace-pre-wrap leading-relaxed relative",
                isEditing && editMode === 'annotate' && "cursor-text select-text"
              )}
              onMouseUp={handleMouseUp}
            >
              {segments.map((segment, i) => (
                segment.annotation ? (
                  <Tooltip key={segment.annotation.id}>
                    <TooltipTrigger asChild>
                      <span
                        className="bg-yellow-500/30 border-b-2 border-yellow-500 cursor-pointer hover:bg-yellow-500/40 transition-colors"
                      >
                        {segment.text}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent
                      side="top"
                      className="max-w-xs"
                    >
                      <div className="space-y-2">
                        <p className="text-sm">{segment.annotation.suggestion}</p>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleRemoveAnnotation(segment.annotation!.id)}
                          className="h-6 px-2 text-xs text-destructive hover:text-destructive"
                        >
                          <Trash2 className="h-3 w-3 mr-1" />
                          Remove
                        </Button>
                      </div>
                    </TooltipContent>
                  </Tooltip>
                ) : (
                  <span key={i}>{segment.text}</span>
                )
              ))}

              {/* Annotation Popover */}
              {showPopover && selectedRange && (
                <div
                  className="absolute z-50"
                  style={{
                    left: `${popoverPosition.x}px`,
                    top: `${popoverPosition.y}px`,
                    transform: 'translateX(-50%)'
                  }}
                >
                  <div className="bg-popover border rounded-lg shadow-lg p-3 w-64">
                    <div className="space-y-2">
                      <p className="text-xs text-muted-foreground">
                        Selected: "<span className="font-medium text-foreground">{selectedRange.text.slice(0, 30)}{selectedRange.text.length > 30 ? '...' : ''}</span>"
                      </p>
                      <Input
                        value={suggestionInput}
                        onChange={(e) => setSuggestionInput(e.target.value)}
                        placeholder="Add your suggestion..."
                        className="h-8 text-sm"
                        autoFocus
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && suggestionInput.trim()) {
                            handleAddAnnotation()
                          }
                          if (e.key === 'Escape') {
                            setShowPopover(false)
                            setSelectedRange(null)
                          }
                        }}
                      />
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={handleAddAnnotation}
                          disabled={!suggestionInput.trim()}
                          className="h-7 text-xs flex-1"
                        >
                          <MessageSquarePlus className="h-3 w-3 mr-1" />
                          Add
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setShowPopover(false)
                            setSelectedRange(null)
                          }}
                          className="h-7 text-xs"
                        >
                          Cancel
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </TooltipProvider>
  )
}

// Thread Card Component with Annotation System and Live Edit
function ThreadCard({
  content,
  onRegenerate,
  isRegenerating
}: {
  content: string[]
  onRegenerate?: (suggestions: string, specificType: string) => void
  isRegenerating?: boolean
}) {
  const [copied, setCopied] = useState(false)
  const [isEditing, setIsEditing] = useState(false)
  const [editMode, setEditMode] = useState<EditMode>('annotate')
  const [editedTweets, setEditedTweets] = useState<string[]>([])
  // Store annotations per tweet index
  const [tweetAnnotations, setTweetAnnotations] = useState<Map<number, Annotation[]>>(new Map())
  const [activePopover, setActivePopover] = useState<{ tweetIndex: number; position: { x: number; y: number }; range: { start: number; end: number; text: string } } | null>(null)
  const [suggestionInput, setSuggestionInput] = useState('')
  const tweetRefs = useRef<(HTMLDivElement | null)[]>([])

  const handleCopy = async () => {
    const textToCopy = editMode === 'edit' && editedTweets.length > 0
      ? editedTweets.join('\n\n---\n\n')
      : content.join('\n\n---\n\n')
    await navigator.clipboard.writeText(textToCopy)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleEdit = () => {
    setIsEditing(true)
    setEditMode('annotate')
    setEditedTweets([...content])
    setTweetAnnotations(new Map())
  }

  const handleCancel = () => {
    setIsEditing(false)
    setEditMode('annotate')
    setEditedTweets([])
    setTweetAnnotations(new Map())
    setActivePopover(null)
    setSuggestionInput('')
  }

  const handleRegenerate = () => {
    if (!onRegenerate) return

    if (editMode === 'annotate') {
      // Combine all annotations from all tweets
      const allSuggestions: string[] = []
      tweetAnnotations.forEach((annotations, tweetIndex) => {
        if (annotations.length > 0) {
          allSuggestions.push(`Tweet ${tweetIndex + 1}:`)
          annotations.forEach((a) => {
            allSuggestions.push(`  - For "${a.text}": ${a.suggestion}`)
          })
        }
      })
      if (allSuggestions.length > 0) {
        onRegenerate(allSuggestions.join('\n'), 'thread')
      }
    } else if (editMode === 'edit') {
      const suggestions = `Improve this thread based on these edits:\n${editedTweets.map((t, i) => `Tweet ${i + 1}: ${t}`).join('\n\n')}`
      onRegenerate(suggestions, 'thread')
    }

    setIsEditing(false)
    setEditedTweets([])
    setTweetAnnotations(new Map())
  }

  const getTotalAnnotations = () => {
    let total = 0
    tweetAnnotations.forEach((annotations) => {
      total += annotations.length
    })
    return total
  }

  const handleTweetChange = (index: number, value: string) => {
    const newTweets = [...editedTweets]
    newTweets[index] = value
    setEditedTweets(newTweets)
  }

  const hasEditChanges = editedTweets.some((t, i) => t !== content[i])
  const totalAnnotations = getTotalAnnotations()
  const canRegenerate = editMode === 'annotate' ? totalAnnotations > 0 : hasEditChanges

  const handleMouseUp = useCallback((tweetIndex: number) => {
    if (!isEditing || editMode !== 'annotate') return

    const selection = window.getSelection()
    if (!selection || selection.isCollapsed || !selection.toString().trim()) {
      return
    }

    const tweetRef = tweetRefs.current[tweetIndex]
    if (!tweetRef) return

    const selectedText = selection.toString().trim()
    const range = selection.getRangeAt(0)

    if (!tweetRef.contains(range.commonAncestorContainer)) {
      return
    }

    // Calculate position
    let startOffset = 0
    const treeWalker = document.createTreeWalker(tweetRef, NodeFilter.SHOW_TEXT, null)

    let node: Node | null
    let found = false
    while ((node = treeWalker.nextNode())) {
      if (node === range.startContainer) {
        startOffset += range.startOffset
        found = true
        break
      }
      startOffset += (node.textContent?.length || 0)
    }

    if (!found) return

    const endOffset = startOffset + range.toString().length

    // Check for overlapping annotations
    const existingAnnotations = tweetAnnotations.get(tweetIndex) || []
    const hasOverlap = existingAnnotations.some(
      (a) => (startOffset < a.end && endOffset > a.start)
    )
    if (hasOverlap) {
      selection.removeAllRanges()
      return
    }

    const rect = range.getBoundingClientRect()
    const containerRect = tweetRef.getBoundingClientRect()

    setActivePopover({
      tweetIndex,
      position: {
        x: rect.left - containerRect.left + rect.width / 2,
        y: rect.bottom - containerRect.top + 8,
      },
      range: { start: startOffset, end: endOffset, text: selectedText }
    })
    setSuggestionInput('')
  }, [isEditing, editMode, tweetAnnotations])

  const handleAddAnnotation = () => {
    if (!activePopover || !suggestionInput.trim()) return

    const newAnnotation: Annotation = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      start: activePopover.range.start,
      end: activePopover.range.end,
      text: activePopover.range.text,
      suggestion: suggestionInput.trim(),
    }

    setTweetAnnotations((prev) => {
      const newMap = new Map(prev)
      const existing = newMap.get(activePopover.tweetIndex) || []
      newMap.set(activePopover.tweetIndex, [...existing, newAnnotation])
      return newMap
    })
    setActivePopover(null)
    setSuggestionInput('')
    window.getSelection()?.removeAllRanges()
  }

  const handleRemoveAnnotation = (tweetIndex: number, annotationId: string) => {
    setTweetAnnotations((prev) => {
      const newMap = new Map(prev)
      const existing = newMap.get(tweetIndex) || []
      newMap.set(tweetIndex, existing.filter((a) => a.id !== annotationId))
      return newMap
    })
  }

  return (
    <TooltipProvider delayDuration={200}>
      <Card className={cn(
        "group transition-all",
        isEditing ? "border-primary ring-1 ring-primary/20" : "hover:border-primary/30"
      )}>
        <CardContent className="p-4">
          <div className="flex items-start justify-between gap-2 mb-3">
            <span className="inline-block text-xs font-medium text-primary bg-primary/10 px-2 py-0.5 rounded">
              Thread ({content.length} tweets)
            </span>
            <div className="flex items-center gap-1">
              {isEditing ? (
                <>
                  {editMode === 'annotate' && totalAnnotations > 0 && (
                    <span className="text-xs text-muted-foreground mr-2">
                      {totalAnnotations} suggestion{totalAnnotations !== 1 ? 's' : ''}
                    </span>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleCancel}
                    className="h-7 px-2 text-xs"
                  >
                    <X className="h-3 w-3 mr-1" />
                    Cancel
                  </Button>
                  <Button
                    variant="default"
                    size="sm"
                    onClick={handleRegenerate}
                    disabled={!canRegenerate || isRegenerating}
                    className="h-7 px-2 text-xs"
                  >
                    {isRegenerating ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <>
                        <RotateCcw className="h-3 w-3 mr-1" />
                        Regenerate
                      </>
                    )}
                  </Button>
                </>
              ) : (
                <>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleEdit}
                    className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Edit content"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleCopy}
                    className="h-7 w-7 opacity-0 group-hover:opacity-100 transition-opacity"
                    title="Copy to clipboard"
                  >
                    {copied ? (
                      <Check className="h-3.5 w-3.5 text-green-500" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                  </Button>
                </>
              )}
            </div>
          </div>

          {isEditing && (
            <div className="mb-3 space-y-2">
              {/* Mode Toggle */}
              <div className="flex gap-1 p-0.5 bg-muted rounded-md w-fit">
                <button
                  onClick={() => setEditMode('annotate')}
                  className={cn(
                    "px-2.5 py-1 text-xs font-medium rounded transition-colors",
                    editMode === 'annotate'
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <MessageSquarePlus className="h-3 w-3 inline mr-1" />
                  Suggest
                </button>
                <button
                  onClick={() => setEditMode('edit')}
                  className={cn(
                    "px-2.5 py-1 text-xs font-medium rounded transition-colors",
                    editMode === 'edit'
                      ? "bg-background text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Pencil className="h-3 w-3 inline mr-1" />
                  Edit
                </button>
              </div>
              <p className="text-xs text-muted-foreground">
                {editMode === 'annotate'
                  ? '✨ Select text in any tweet to add suggestions. Hover over highlights to see or remove them.'
                  : '✏️ Edit the tweets directly. Your changes will guide the AI regeneration.'}
              </p>
            </div>
          )}

          <div className="space-y-3">
            {content.map((tweet, i) => {
              const annotations = tweetAnnotations.get(i) || []
              const segments = getTextSegments(tweet, annotations)

              return (
                <div key={i} className="flex gap-3">
                  <div className="flex flex-col items-center">
                    <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary text-xs font-medium text-primary-foreground">
                      {i + 1}
                    </div>
                    {i < content.length - 1 && (
                      <div className="w-0.5 flex-1 bg-border mt-1" />
                    )}
                  </div>

                  {isEditing && editMode === 'edit' ? (
                    <Textarea
                      value={editedTweets[i] || ''}
                      onChange={(e) => handleTweetChange(i, e.target.value)}
                      className="flex-1 text-sm min-h-[60px] resize-none leading-relaxed"
                    />
                  ) : (
                    <div
                      ref={(el) => { tweetRefs.current[i] = el }}
                      className={cn(
                        "flex-1 text-sm leading-relaxed pb-2 relative",
                        isEditing && editMode === 'annotate' && "cursor-text select-text"
                      )}
                      onMouseUp={() => handleMouseUp(i)}
                    >
                      {segments.map((segment, j) => (
                        segment.annotation ? (
                          <Tooltip key={segment.annotation.id}>
                            <TooltipTrigger asChild>
                              <span
                                className="bg-yellow-500/30 border-b-2 border-yellow-500 cursor-pointer hover:bg-yellow-500/40 transition-colors"
                              >
                                {segment.text}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent side="top" className="max-w-xs">
                              <div className="space-y-2">
                                <p className="text-sm">{segment.annotation.suggestion}</p>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleRemoveAnnotation(i, segment.annotation!.id)}
                                  className="h-6 px-2 text-xs text-destructive hover:text-destructive"
                                >
                                  <Trash2 className="h-3 w-3 mr-1" />
                                  Remove
                                </Button>
                              </div>
                            </TooltipContent>
                          </Tooltip>
                        ) : (
                          <span key={j}>{segment.text}</span>
                        )
                      ))}

                      {/* Annotation Popover for this tweet */}
                      {activePopover && activePopover.tweetIndex === i && (
                        <div
                          className="absolute z-50"
                          style={{
                            left: `${activePopover.position.x}px`,
                            top: `${activePopover.position.y}px`,
                            transform: 'translateX(-50%)'
                          }}
                        >
                          <div className="bg-popover border rounded-lg shadow-lg p-3 w-64">
                            <div className="space-y-2">
                              <p className="text-xs text-muted-foreground">
                                Selected: "<span className="font-medium text-foreground">{activePopover.range.text.slice(0, 30)}{activePopover.range.text.length > 30 ? '...' : ''}</span>"
                              </p>
                              <Input
                                value={suggestionInput}
                                onChange={(e) => setSuggestionInput(e.target.value)}
                                placeholder="Add your suggestion..."
                                className="h-8 text-sm"
                                autoFocus
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter' && suggestionInput.trim()) {
                                    handleAddAnnotation()
                                  }
                                  if (e.key === 'Escape') {
                                    setActivePopover(null)
                                  }
                                }}
                              />
                              <div className="flex gap-2">
                                <Button
                                  size="sm"
                                  onClick={handleAddAnnotation}
                                  disabled={!suggestionInput.trim()}
                                  className="h-7 text-xs flex-1"
                                >
                                  <MessageSquarePlus className="h-3 w-3 mr-1" />
                                  Add
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => setActivePopover(null)}
                                  className="h-7 text-xs"
                                >
                                  Cancel
                                </Button>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>
    </TooltipProvider>
  )
}
