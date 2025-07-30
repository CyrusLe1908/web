document.addEventListener('DOMContentLoaded', function() {
    const loadingOverlay = document.getElementById('loadingOverlay');

    if (loadingOverlay) {
        // Hàm để hiển thị lớp phủ tải
        window.showLoading = function() {
            loadingOverlay.style.display = 'flex'; // Sử dụng flex để căn giữa
        };

        // Hàm để ẩn lớp phủ tải
        window.hideLoading = function() {
            loadingOverlay.style.display = 'none';
        };

        // Ẩn lớp phủ khi trang tải xong ban đầu (tránh trường hợp nó vẫn hiện)
        hideLoading();
    }
});