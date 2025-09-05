document.addEventListener('DOMContentLoaded', () => {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    const switchTab = (tabId) => {
        tabButtons.forEach(btn => btn.classList.remove('active'));
        tabContents.forEach(content => content.classList.remove('active'));
        
        const activeBtn = document.querySelector(`.tab-btn[data-tab="${tabId}"]`);
        const activeContent = document.getElementById(tabId);
        
        if (activeBtn) activeBtn.classList.add('active');
        if (activeContent) activeContent.classList.add('active');
    };

    tabButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            if (!btn.classList.contains('disabled')) {
                switchTab(btn.dataset.tab);
                if (btn.dataset.tab === 'dashboard-tab') loadDashboardData();
                if (btn.dataset.tab === 'verify-orders-tab') loadOrdersData();
                if (btn.dataset.tab === 'manage-status-tab') loadOrdersDataForManage();
            }
        });
    });

    const loadDashboardData = async () => {
        try {
            const response = await fetch('/api/dashboard');
            const data = await response.json();

            if (data.error) {
                console.error(data.error);
                return;
            }

            document.getElementById('total-pedidos').textContent = data.total_pedidos;
            document.getElementById('pedidos-prontos').textContent = data.pedidos_prontos;
            document.getElementById('pedidos-em-producao').textContent = data.pedidos_em_producao;
            document.getElementById('pedidos-em-atencao').textContent = data.pedidos_em_atencao;
            document.getElementById('pedidos-atrasados').textContent = data.pedidos_atrasados;

            createModelChart(data.model_counts);
            createStatusChart(data.status_counts);
            
        } catch (error) {
            console.error('Erro ao carregar dados do dashboard:', error);
        }
    };

    const createModelChart = (data) => {
        const ctx = document.getElementById('modelChart').getContext('2d');
        const labels = Object.keys(data);
        const values = Object.values(data);
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Pedidos em Produção por Modelo',
                    data: values,
                    backgroundColor: '#00c49f',
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: { beginAtZero: true },
                    x: { ticks: { color: 'white' } },
                    y: { ticks: { color: 'white' } }
                }
            }
        });
    };

    const createStatusChart = (data) => {
        const ctx = document.getElementById('statusChart').getContext('2d');
        const labels = Object.keys(data);
        const values = Object.values(data);
        const colors = [
            '#00c49f', '#ff6384', '#ff9f40', '#ffcd56', '#4bc0c0', '#9966ff', '#c9cbcf'
        ];
        new Chart(ctx, {
            type: 'pie',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Proporção de Status',
                    data: values,
                    backgroundColor: colors,
                }]
            },
            options: {
                responsive: true,
            }
        });
    };

    const createOrderBtn = document.querySelector('.create-btn');
    const generateIdBtn = document.getElementById('generate-id-btn');

    if (generateIdBtn) {
        generateIdBtn.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/generate_id');
                const data = await response.json();
                document.getElementById('order-id').value = data.id;
            } catch (error) {
                alert('Erro ao gerar ID.');
            }
        });
    }

    if (createOrderBtn) {
        createOrderBtn.addEventListener('click', async () => {
            const orderData = {
                Ids: document.getElementById('order-id').value,
                'Nome do pedido': document.getElementById('order-name').value,
                Modelo: document.getElementById('order-model').value,
                'Detalhes do Produto': document.getElementById('product-details').value,
                'link google drive (layout)': document.getElementById('drive-link').value,
                Status: document.getElementById('order-status').value,
                Data: document.getElementById('entry-date').value,
                'Data de Saida': document.getElementById('exit-date').value
            };

            try {
                const response = await fetch('/api/create_order', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(orderData)
                });
                const result = await response.json();

                if (response.ok) {
                    alert(result.message);
                    document.querySelector('.form-container').reset();
                    loadOrdersData();
                    loadDashboardData();
                } else {
                    alert(`Erro: ${result.message}`);
                }
            } catch (error) {
                console.error('Erro ao criar pedido:', error);
                alert('Erro de conexão com o servidor.');
            }
        });
    }

    const ordersTableBody = document.getElementById('orders-table-body');
    const loadOrdersData = async () => {
        try {
            const response = await fetch('/api/orders');
            const orders = await response.json();
            ordersTableBody.innerHTML = '';
            orders.forEach(order => {
                const row = `
                    <tr>
                        <td>${order.Ids}</td>
                        <td>${order['Nome do pedido']}</td>
                        <td>${order.Modelo}</td>
                        <td>${order['Detalhes do Produto']}</td>
                        <td><a href="${order['link google drive (layout)']}" target="_blank">Abrir Drive</a></td>
                        <td>${order.Status}</td>
                        <td>${order.Data}</td>
                        <td>${order['Data de Saida']}</td>
                    </tr>
                `;
                ordersTableBody.innerHTML += row;
            });
        } catch (error) {
            console.error('Erro ao carregar pedidos:', error);
        }
    };
    
    const manageTableBody = document.getElementById('manage-table-body');
    const updateStatusBtn = document.getElementById('update-status-btn');
    const newStatusManageSelect = document.getElementById('new-status-manage');

    const loadOrdersDataForManage = async () => {
        try {
            const response = await fetch('/api/orders');
            const orders = await response.json();
            manageTableBody.innerHTML = '';
            orders.forEach(order => {
                const row = `
                    <tr>
                        <td><input type="checkbox" data-id="${order.Ids}"></td>
                        <td>${order.Ids}</td>
                        <td>${order['Nome do pedido']}</td>
                        <td>${order.Status}</td>
                    </tr>
                `;
                manageTableBody.innerHTML += row;
            });
        } catch (error) {
            console.error('Erro ao carregar pedidos para gerenciar:', error);
        }
    };

    if (updateStatusBtn) {
        updateStatusBtn.addEventListener('click', async () => {
            const selectedCheckboxes = document.querySelectorAll('#manage-table-body input[type="checkbox"]:checked');
            if (selectedCheckboxes.length === 0) {
                alert('Selecione pelo menos um pedido.');
                return;
            }

            const newStatus = newStatusManageSelect.value;
            const updatePromises = [];

            for (const checkbox of selectedCheckboxes) {
                const orderId = checkbox.dataset.id;
                const promise = fetch('/api/update_status', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: orderId, status: newStatus })
                })
                .then(response => response.json());

                updatePromises.push(promise);
            }

            try {
                await Promise.all(updatePromises);
                alert('Status(es) atualizado(s) com sucesso!');
                loadOrdersDataForManage();
                loadDashboardData();
                loadOrdersData();
            } catch (error) {
                console.error('Erro ao atualizar status:', error);
                alert('Ocorreu um erro ao atualizar um ou mais pedidos.');
            }
        });
    }

    const searchInput = document.getElementById('search-input');
    const statusFilter = document.getElementById('status-filter');
    const searchBtn = document.getElementById('search-btn');
    const filterBtn = document.getElementById('filter-btn');
    const reloadBtn = document.getElementById('reload-btn');

    const filterAndSearch = async () => {
        const query = searchInput.value.toLowerCase();
        const status = statusFilter.value;
        
        const response = await fetch('/api/orders');
        const orders = await response.json();
        
        const filteredOrders = orders.filter(order => {
            const matchesQuery = order.Ids.toLowerCase().includes(query) || order['Nome do pedido'].toLowerCase().includes(query);
            const matchesStatus = status === 'Todos' || order.Status.includes(status);
            return matchesQuery && matchesStatus;
        });
        
        ordersTableBody.innerHTML = '';
        filteredOrders.forEach(order => {
            const row = `
                <tr>
                    <td>${order.Ids}</td>
                    <td>${order['Nome do pedido']}</td>
                    <td>${order.Modelo}</td>
                    <td>${order['Detalhes do Produto']}</td>
                    <td><a href="${order['link google drive (layout)']}" target="_blank">Abrir Drive</a></td>
                    <td>${order.Status}</td>
                    <td>${order.Data}</td>
                    <td>${order['Data de Saida']}</td>
                </tr>
            `;
            ordersTableBody.innerHTML += row;
        });
    };

    if (searchBtn) searchBtn.addEventListener('click', filterAndSearch);
    if (filterBtn) filterBtn.addEventListener('click', filterAndSearch);
    if (reloadBtn) reloadBtn.addEventListener('click', () => {
        loadOrdersData();
        loadDashboardData();
        searchInput.value = '';
        statusFilter.value = 'Todos';
    });

    document.getElementById('current-date').textContent = new Date().toLocaleDateString('pt-BR');
    loadDashboardData();
    loadOrdersData();
});