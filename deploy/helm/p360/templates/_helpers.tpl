{{- define "p360.labels" -}}
app.kubernetes.io/part-of: p360
app.kubernetes.io/managed-by: {{ .Release.Service }}
p360/target: {{ .Values.target }}
{{- end -}}
