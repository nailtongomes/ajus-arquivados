import streamlit as st
import pandas as pd
import json
import numpy as np
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go

# Configuração da página
st.set_page_config(
    page_title="Explorador de Dados Jurídicos",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)


@st.cache_data
def load_data(file_path):
    """Carrega e processa os dados do arquivo parquet"""
    try:
        df = pd.read_parquet(file_path)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar arquivo: {e}")
        return None


def parse_movimentacoes(movimentacoes_str):
    """Parse das movimentações JSON"""
    if pd.isna(movimentacoes_str):
        return []
    try:
        return json.loads(movimentacoes_str)
    except:
        return []


def get_all_movimentacoes_text(movimentacoes_str):
    """Retorna todas as movimentações concatenadas para busca"""
    movimentacoes = parse_movimentacoes(movimentacoes_str)
    if not movimentacoes:
        return ""

    # Concatena todas as descrições das movimentações
    todas_descricoes = " ".join([mov.get('descricao', '') for mov in movimentacoes])
    return todas_descricoes.lower()


def get_movimentacao_by_position(movimentacoes_str, position):
    """Retorna movimentação por posição (0=última, 1=penúltima, 2=antepenúltima)"""
    movimentacoes = parse_movimentacoes(movimentacoes_str)
    if len(movimentacoes) > position:
        return movimentacoes[position].get('descricao', 'N/A')
    return 'N/A'


def check_processo_arquivado(movimentacoes_str):
    """Verifica se processo está arquivado baseado nas últimas 3 movimentações"""
    movimentacoes = parse_movimentacoes(movimentacoes_str)
    if not movimentacoes:
        return False

    # Pega as últimas 3 movimentações
    ultimas_movs = movimentacoes[:3]

    # falsos positivos
    keywords = ['conclusos', 'recebidos', 'desarquivado']
    if any(keyword in ultimas_movs[0].get('descricao', '').lower() for keyword in keywords):
        return False

    keywords = ['baixa definitiva', 'arquivado', 'para a instância de origem']
    for mov in ultimas_movs:
        descricao = mov.get('descricao', '').lower()
        if any(keyword in descricao for keyword in keywords):
            return True

    return False


def check_processo_nao_encontrado(row):
    """Verifica se processo não foi encontrado"""
    return pd.isna(row['ultima_movimentacao']) and pd.isna(row['data_ultima_movimentacao'])


def check_processo_ativo(row):
    """Verifica se processo está ativo"""
    return not check_processo_nao_encontrado(row) and not check_processo_arquivado(row['movimentacoes'])


def format_data(data_str):
    """Formata data para exibição"""
    if pd.isna(data_str):
        return "N/A"
    return data_str


def main():
    st.title("⚖️ Explorador de Dados - AJUS-SMB")
    st.markdown("**Análise rápida e eficiente de processos jurídicos**")

    # Upload de arquivo
    #uploaded_file = st.file_uploader(
        #"📁 Carregue o arquivo .parquet",
        #type=['parquet'],
        #help="Selecione o arquivo .parquet com os dados dos processos"
    #)
    uploaded_file = 'db/db.parquet'

    if uploaded_file is not None:
        # Carrega os dados
        df = pd.read_parquet(uploaded_file)

        if df is not None:
            # Processa classificações
            df['arquivado'] = df['movimentacoes'].apply(check_processo_arquivado)
            df['nao_encontrado'] = df.apply(check_processo_nao_encontrado, axis=1)
            df['ativo'] = df.apply(check_processo_ativo, axis=1)

            # Sidebar com filtros
            st.sidebar.header("🔍 Filtros")

            # Contadores
            total_processos = len(df)
            arquivados = df['arquivado'].sum()
            nao_encontrados = df['nao_encontrado'].sum()
            ativos = df['ativo'].sum()

            st.sidebar.markdown("### 📊 Resumo Geral")
            st.sidebar.metric("Total de Processos", total_processos)
            st.sidebar.metric("Processos Ativos", ativos, delta=f"{(ativos / total_processos * 100):.1f}%")
            st.sidebar.metric("Processos Arquivados", arquivados, delta=f"{(arquivados / total_processos * 100):.1f}%")
            st.sidebar.metric("Não Encontrados", nao_encontrados,
                              delta=f"{(nao_encontrados / total_processos * 100):.1f}%")

            st.sidebar.markdown("---")

            # Filtros principais
            st.sidebar.markdown("### 🎯 Filtros de Status")

            # Radio button para seleção exclusiva
            status_selecionado = st.sidebar.radio(
                "Selecione o status dos processos:",
                options=["📦 Processos Arquivados", "✅ Processos Ativos", "❌ Não Encontrados"],
                index=0  # Padrão: Arquivados
            )

            # Aplicar filtros baseado na seleção
            df_filtrado = df.copy()

            if status_selecionado == "✅ Processos Ativos":
                df_filtrado = df_filtrado[df_filtrado['ativo'] == True]
            elif status_selecionado == "📦 Processos Arquivados":
                df_filtrado = df_filtrado[df_filtrado['arquivado'] == True]
            elif status_selecionado == "❌ Não Encontrados":
                df_filtrado = df_filtrado[df_filtrado['nao_encontrado'] == True]

            # Filtro por tribunal
            tribunais = df['tribunal'].unique()
            tribunal_selecionado = st.sidebar.selectbox(
                "🏛️ Filtrar por Tribunal",
                options=['Todos'] + list(tribunais)
            )

            # Filtro por tribunal
            if tribunal_selecionado != 'Todos':
                df_filtrado = df_filtrado[df_filtrado['tribunal'] == tribunal_selecionado]

            st.sidebar.markdown("### 🔍 Filtro por Movimentação")

            # Campo de busca por movimentação
            termo_movimentacao = st.sidebar.text_input(
                "🔎 Buscar por termo na movimentação:",
                placeholder="Ex: sentença, recurso, arquivado...",
                help="Busca em todas as movimentações do processo"
            )

            # Aplicar filtro de movimentação se houver termo
            if termo_movimentacao:
                termo_lower = termo_movimentacao.lower().strip()
                if termo_lower:
                    # Adiciona coluna temporária com todas as movimentações
                    df_filtrado['todas_movimentacoes'] = df_filtrado['movimentacoes'].apply(get_all_movimentacoes_text)

                    # Filtra processos que contém o termo
                    df_filtrado = df_filtrado[df_filtrado['todas_movimentacoes'].str.contains(termo_lower, na=False)]

                    # Remove coluna temporária
                    df_filtrado = df_filtrado.drop(columns=['todas_movimentacoes'])

                    # Mostra feedback do filtro
                    st.sidebar.success(f"🎯 Filtrado por: '{termo_movimentacao}'")


            # Exibição principal
            col1, col2 = st.columns([2, 1])

            #with col1:
            st.header(f"📋 Dados Filtrados ({len(df_filtrado)} processos)")

            # Configurar colunas para exibição
            colunas_exibir = ['numero_processo', 'tribunal', 'data_ultima_movimentacao', 'ultima_movimentacao']

            # Formatação dos dados para exibição
            df_display = df_filtrado[colunas_exibir].copy()

            # Adicionar penúltima e antepenúltima movimentação
            df_display['penultima_movimentacao'] = df_filtrado['movimentacoes'].apply(
                lambda x: get_movimentacao_by_position(x, 1)
            )
            df_display['antepenultima_movimentacao'] = df_filtrado['movimentacoes'].apply(
                lambda x: get_movimentacao_by_position(x, 2)
            )

            df_display['data_ultima_movimentacao'] = df_display['data_ultima_movimentacao'].apply(format_data)
            df_display['ultima_movimentacao'] = df_display['ultima_movimentacao'].fillna('N/A')

            # Renomear colunas para exibição
            df_display.columns = [
                'Número do Processo',
                'Tribunal',
                'Data da Última Movimentação',
                'Última Movimentação',
                'Penúltima Movimentação',
                'Antepenúltima Movimentação'
            ]

            st.dataframe(
                df_display,
                use_container_width=True,
                height=400,
                width=600,
                hide_index=True
            )

            # Botão de download
            csv_data = df_filtrado.to_csv(index=False)
            st.download_button(
                label="📥 Baixar dados filtrados (CSV)",
                data=csv_data,
                file_name=f"processos_filtrados_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv"
            )

            # with col2:
                #st.header("📈 Análises Rápidas")

                # Gráfico de pizza - Status dos processos
                #status_counts = pd.Series({
                #    'Ativos': ativos,
                #    'Arquivados': arquivados,
                #    'Não Encontrados': nao_encontrados
                #})

                #fig_pie = px.pie(
                #    values=status_counts.values,
                #    names=status_counts.index,
                #    title="Distribuição por Status",
                #    color_discrete_map={
                #        'Ativos': '#2E8B57',
                #        'Arquivados': '#FF6347',
                #        'Não Encontrados': '#FFD700'
                #    }
                #)
                #fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                #st.plotly_chart(fig_pie, use_container_width=True)

                # Gráfico de barras - Por tribunal
                #tribunal_counts = df['tribunal'].value_counts()
                #fig_bar = px.bar(
                    #x=tribunal_counts.index,
                    #y=tribunal_counts.values,
                    #title="Processos por Tribunal",
                    #labels={'x': 'Tribunal', 'y': 'Quantidade'}
                #)
                #fig_bar.update_xaxes(tickangle=45)
                #st.plotly_chart(fig_bar, use_container_width=True)

            # Seção de detalhes do processo selecionado
            st.header("🔍 Detalhes do Processo")

            if len(df_filtrado) > 0:
                processo_selecionado = st.selectbox(
                    "Selecione um processo para ver detalhes:",
                    options=df_filtrado['numero_processo'].tolist(),
                    key="processo_select"
                )

                if processo_selecionado:
                    processo_data = df_filtrado[df_filtrado['numero_processo'] == processo_selecionado].iloc[0]

                    col1, col2 = st.columns(2)

                    with col1:
                        st.subheader("ℹ️ Informações Básicas")
                        st.write(f"**Número:** {processo_data['numero_processo']}")
                        st.write(f"**Tribunal:** {processo_data['tribunal']}")
                        st.write(
                            f"**Última Movimentação:** {processo_data['ultima_movimentacao'] if pd.notna(processo_data['ultima_movimentacao']) else 'N/A'}")
                        st.write(f"**Data:** {format_data(processo_data['data_ultima_movimentacao'])}")

                    with col2:
                        st.subheader("🏷️ Status")
                        if processo_data['ativo']:
                            st.success("✅ Processo Ativo")
                        elif processo_data['arquivado']:
                            st.error("📦 Processo Arquivado")
                        elif processo_data['nao_encontrado']:
                            st.warning("❌ Processo Não Encontrado")

                    # Histórico de movimentações
                    st.subheader("📜 Histórico de Movimentações")
                    movimentacoes = parse_movimentacoes(processo_data['movimentacoes'])

                    if movimentacoes:
                        # Exibe movimentações em lista simples
                        for i, mov in enumerate(movimentacoes):
                            # Container com borda sutil para cada movimentação
                            with st.container():
                                col_data, col_desc = st.columns([1, 3])

                                with col_data:
                                    st.write(f"**{i + 1}.** {mov.get('data', 'Data não informada')}")

                                with col_desc:
                                    st.write(mov.get('descricao', 'Descrição não informada'))

                                # Linha separadora visual
                                if i < len(movimentacoes) - 1:
                                    st.divider()
                    else:
                        st.info("Nenhuma movimentação encontrada para este processo.")

            # Métricas de performance
            st.sidebar.markdown("---")
            st.sidebar.markdown("### ⚡ Métricas de Performance")
            st.sidebar.info(f"Dados processados: {len(df):,} registros")
            st.sidebar.info(f"Filtros aplicados: {len(df_filtrado):,} resultados")

        else:
            st.error("Não foi possível carregar os dados do arquivo.")

    else:
        st.info("👆 Carregue um arquivo .parquet para começar a análise")

        # Exemplo de estrutura esperada
        st.markdown("### 📋 Estrutura de Dados Esperada")
        st.code("""
        Colunas necessárias:
        - id: Identificador único
        - unique_key: Chave única do processo
        - tribunal: Nome do tribunal
        - numero_processo: Número do processo
        - ultima_movimentacao: Última movimentação
        - data_ultima_movimentacao: Data da última movimentação
        - movimentacoes: JSON com histórico de movimentações
        """)


if __name__ == "__main__":
    main()