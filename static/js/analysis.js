document.addEventListener('DOMContentLoaded', function() {
    const eventSelect = document.getElementById('event_id');
    if (eventSelect) {
        eventSelect.addEventListener('change', function() {
            let url = new URL(window.location.href);
            
            url.searchParams.set('event_id', this.value);
            
            url.searchParams.delete('analysis_id');
            
            window.location.href = url.toString();
        });
    }
    
    const analysisSelect = document.getElementById('analysis_id');
    if (analysisSelect) {
        analysisSelect.addEventListener('change', function() {
            let url = new URL(window.location.href);
            
            url.searchParams.set('analysis_id', this.value);
            
            window.location.href = url.toString();
        });
    }
});