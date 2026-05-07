<script setup lang="ts">
import { useEditor, EditorContent } from '@tiptap/vue-3';
import StarterKit from '@tiptap/starter-kit';
import { watch } from 'vue';

const props = defineProps<{ modelValue: string; readonly?: boolean }>();
const emit = defineEmits<{ (e: 'update:modelValue', v: string): void }>();

const editor = useEditor({
  content: props.modelValue,
  extensions: [StarterKit],
  editable: !props.readonly,
  onUpdate({ editor }) {
    emit('update:modelValue', editor.getHTML());
  },
});

watch(() => props.modelValue, (v) => {
  if (editor.value && v !== editor.value.getHTML()) editor.value.commands.setContent(v);
});

watch(() => props.readonly, (r) => {
  editor.value?.setEditable(!r);
});
</script>

<template>
  <div style="border:1px solid #d9d9d9;border-radius:6px;padding:12px;min-height:300px">
    <editor-content :editor="editor" />
  </div>
</template>

<style>
.ProseMirror { outline: none; min-height: 280px; line-height: 1.7; }
.ProseMirror h1, .ProseMirror h2, .ProseMirror h3 { margin: 16px 0 8px; }
.ProseMirror p { margin: 0 0 8px; }
</style>
